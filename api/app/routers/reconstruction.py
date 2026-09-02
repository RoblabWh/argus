import os
import logging
from datetime import datetime, timezone
from typing import Optional, Tuple

import pyexifinfo as p
import redis
import json
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

import app.crud.report as report_crud
import app.services.events as events_service
from app.database import get_db
from app.config import config
from app.schemas.report import (
    ReportCreate, ReportOut, ReconstructionSettings, ReconstructionReportOut,
    KeyframeShareRequest,
)
from app.services.drz_backend_sharing import send_photo_to_iais
from app.services.celery_app import celery_app
from app.services.camera_config_service import extract_video_metadata

router = APIRouter(prefix="/reconstruction", tags=["Reconstruction"])

r = redis.Redis(host=config.REDIS_HOST, port=config.REDIS_PORT, db=0)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Paths as seen from inside each container (same shared volume, different mount points)
API_REPORTS_PATH = "/api/reports_data"
STELLA_REPORTS_PATH = "/data/reports"


def _keyframes_dir(report_id: int) -> str:
    return os.path.join(API_REPORTS_PATH, str(report_id), "reconstruction", "keyframes")


def _list_keyframe_files(report_id: int) -> list[str]:
    """
    Keyframe image filenames in trajectory order.

    Stella names them image0, image1, image10, ... so they must be sorted by the numeric
    suffix, not lexicographically — the resulting order matches keyframe_trajectory.txt
    line by line, which is what the pose pairing and every keyframe index rely on.
    """
    keyframes_dir = _keyframes_dir(report_id)
    if not os.path.isdir(keyframes_dir):
        return []
    return sorted(
        [f for f in os.listdir(keyframes_dir)
         if f.lower().endswith((".jpg", ".jpeg", ".png")) and f.startswith("image")],
        key=lambda x: int(os.path.splitext(x)[0].replace("image", "")),
    )


def _resolve_keyframe(report_id: int, index: int) -> tuple[str, str]:
    """(absolute path, filename) of one keyframe, or 404."""
    files = _list_keyframe_files(report_id)
    if index < 0 or index >= len(files):
        raise HTTPException(status_code=404, detail=f"Keyframe {index} not found")
    return os.path.join(_keyframes_dir(report_id), files[index]), files[index]

class ReconstructionReportCreate(BaseModel):
    group_id: int
    title: str
    description: str = ""


# ── Create ────────────────────────────────────────────────────────────────────

@router.post("/", response_model=ReportOut)
def create_reconstruction_report(data: ReconstructionReportCreate, db: Session = Depends(get_db)):
    """Create a new 360° reconstruction report."""
    report = report_crud.create(db, ReportCreate(
        group_id=data.group_id,
        title=data.title,
        description=data.description,
        type="reconstruction_360",
        status="unprocessed",
    ))
    report_crud.create_reconstruction_report(db, report.report_id)
    return report


# ── Start processing ──────────────────────────────────────────────────────────

@router.post("/{report_id}/process", response_model=ReportOut)
def start_reconstruction(
    report_id: int,
    settings: ReconstructionSettings,
    db: Session = Depends(get_db),
):
    """Dispatch reconstruction task to the stella worker."""
    reconstruction = report_crud.get_reconstruction_report(db, report_id)
    if not reconstruction:
        raise HTTPException(status_code=404, detail="Reconstruction report not found")
    if not reconstruction.video_path:
        raise HTTPException(status_code=400, detail="No video uploaded for this report")

    # Stella-side paths (volume mounted at /data/reports inside stella container)
    video_path_stella = os.path.join(STELLA_REPORTS_PATH, reconstruction.video_path)
    results_path_stella = os.path.join(STELLA_REPORTS_PATH, str(report_id), "reconstruction")

    # Ensure results directory exists (API-side path)
    os.makedirs(os.path.join(API_REPORTS_PATH, str(report_id), "reconstruction"), exist_ok=True)

    options = {
        "preset": settings.preset,
        "frame_step": settings.frame_step,
        "flip_video": settings.flip_video,
    }

    task = celery_app.signature(
        "reconstruction_stella.run",
        args=[report_id, video_path_stella, results_path_stella, options, settings.config_overrides],
        queue="reconstruction_stella",
    ).apply_async()

    r.set(f"reconstruction:{report_id}:task_id", task.id)
    r.set(f"reconstruction:{report_id}:status", "queued")
    r.set(f"reconstruction:{report_id}:progress", 0)
    r.set(f"reconstruction:{report_id}:message", "Task queued")
    events_service.publish_event(
        r, report_id, events_service.EVENT_RECONSTRUCTION_STATUS,
        status="queued", progress=0, message="Task queued",
    )

    report_crud.update_reconstruction_report(db, report_id, processing_settings=settings.model_dump())
    return report_crud.update_process(db, report_id, "queued", 0.0)


# ── Status polling ────────────────────────────────────────────────────────────

@router.get("/{report_id}/status", response_model=dict)
def get_reconstruction_status(report_id: int, db: Session = Depends(get_db)):
    """Poll the current status and progress from Redis."""
    # Pure read — the stella worker owns the DB status via its progress updates
    # and the /complete callback; the status watchdog covers crashed tasks.
    state = events_service.read_reconstruction_state(r, report_id)
    if state is None:
        raise HTTPException(status_code=404, detail="No reconstruction status found for this report")
    return state


# ── Video path update (called by stella worker after preprocessing) ───────────

class SetVideoPathRequest(BaseModel):
    video_path: str

@router.post("/{report_id}/set_video_path")
def set_video_path(report_id: int, body: SetVideoPathRequest, db: Session = Depends(get_db)):
    """Called by the stella worker to update the DB video_path after flip preprocessing."""
    reconstruction = report_crud.get_reconstruction_report(db, report_id)
    if not reconstruction:
        raise HTTPException(status_code=404, detail="Reconstruction report not found")
    report_crud.update_reconstruction_report(db, report_id, video_path=body.video_path)
    return {"ok": True}


# ── Completion callback (called by stella worker) ─────────────────────────────

@router.post("/{report_id}/complete")
def complete_reconstruction(report_id: int, db: Session = Depends(get_db)):
    """
    Called by the stella worker when processing finishes.
    Reads output files and finalizes the DB entry.
    """
    reconstruction = report_crud.get_reconstruction_report(db, report_id)
    if not reconstruction:
        raise HTTPException(status_code=404, detail="Reconstruction report not found")

    results_dir = os.path.join(API_REPORTS_PATH, str(report_id), "reconstruction")
    keyframes_dir = os.path.join(results_dir, "keyframes")
    trajectory_file = os.path.join(results_dir, "keyframe_trajectory.txt")
    dense_ply = os.path.join(results_dir, "dense.ply")

    # Count keyframes on disk
    keyframe_count = 0
    if os.path.isdir(keyframes_dir):
        keyframe_count = len([
            f for f in os.listdir(keyframes_dir)
            if f.lower().endswith((".jpg", ".jpeg", ".png"))
        ])

    has_dense = os.path.isfile(dense_ply)

    report_crud.update_reconstruction_report(
        db, report_id,
        keyframe_count=keyframe_count,
        has_dense_pointcloud=has_dense,
    )
    report_crud.update_process(db, report_id, "completed", 100.0)

    # Clean up Redis task key
    r.delete(f"reconstruction:{report_id}:task_id")

    events_service.publish_event(
        r, report_id, events_service.EVENT_RECONSTRUCTION_STATUS,
        status="completed", progress=100,
        message="Reconstruction finalized",
        data={"keyframe_count": keyframe_count, "has_dense_pointcloud": has_dense},
    )
    events_service.publish_event(
        r, report_id, events_service.EVENT_REPORT_STATUS,
        status="completed", progress=100.0,
    )

    logger.info(f"Reconstruction complete for report {report_id}: {keyframe_count} keyframes, dense={has_dense}")
    return {"message": "Reconstruction finalized", "report_id": report_id, "keyframe_count": keyframe_count}


# ── Results ───────────────────────────────────────────────────────────────────

@router.get("/{report_id}/results", response_model=dict)
def get_reconstruction_results(report_id: int, db: Session = Depends(get_db)):
    """
    Returns keyframes with 6-DOF poses parsed from keyframe_trajectory.txt (TUM format),
    plus point cloud URLs if available.
    """
    reconstruction = report_crud.get_reconstruction_report(db, report_id)
    if not reconstruction:
        raise HTTPException(status_code=404, detail="Reconstruction report not found")

    results_dir = os.path.join(API_REPORTS_PATH, str(report_id), "reconstruction")
    trajectory_file = os.path.join(results_dir, "keyframe_trajectory.txt")

    if not os.path.isdir(results_dir):
        raise HTTPException(status_code=404, detail="Reconstruction results not found. Has processing completed?")

    # Parse TUM trajectory: timestamp tx ty tz qx qy qz qw
    # Entries are in ascending timestamp order — same order as the saved keyframe images.
    poses = []
    if os.path.isfile(trajectory_file):
        with open(trajectory_file, "r") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split()
                if len(parts) == 8:
                    ts, tx, ty, tz, qx, qy, qz, qw = parts
                    poses.append({
                        "timestamp": float(ts),
                        "tx": float(tx), "ty": float(ty), "tz": float(tz),
                        "qx": float(qx), "qy": float(qy), "qz": float(qz), "qw": float(qw),
                    })

    # Pair keyframes with poses by position — stella saves keyframe images as sequential
    # numbered files (000001.jpg, …), matching the order of entries in the trajectory file.
    keyframes = []
    for idx, filename in enumerate(_list_keyframe_files(report_id)):
        pose = poses[idx] if idx < len(poses) else {}
        keyframes.append({
            "filename": filename,
            "url": f"/reports_data/{report_id}/reconstruction/keyframes/{filename}",
            **pose,
        })

    result: dict = {
        "report_id": report_id,
        "keyframe_count": len(keyframes),
        "keyframes": keyframes,
        "has_dense_pointcloud": reconstruction.has_dense_pointcloud,
        "sparse_pointcloud_url": f"/reports_data/{report_id}/reconstruction/sparse.ply"
            if os.path.isfile(os.path.join(results_dir, "sparse.ply")) else None,
        "dense_pointcloud_url": f"/reports_data/{report_id}/reconstruction/dense.ply"
            if reconstruction.has_dense_pointcloud else None,
        # Manually picked coordinates, keyed by keyframe index (as a string)
        "keyframe_geo": reconstruction.keyframe_geo or {},
    }
    return result


# ── Keyframe sharing ──────────────────────────────────────────────────────────

@router.get("/{report_id}/keyframes/{index}/download")
def download_keyframe(report_id: int, index: int, db: Session = Depends(get_db)):
    """Download a single keyframe panorama with a readable filename."""
    if not report_crud.get_reconstruction_report(db, report_id):
        raise HTTPException(status_code=404, detail="Reconstruction report not found")

    path, filename = _resolve_keyframe(report_id, index)
    ext = os.path.splitext(filename)[1].lower() or ".jpg"
    media_type = "image/png" if ext == ".png" else "image/jpeg"
    return FileResponse(
        path,
        media_type=media_type,
        filename=f"report{report_id}_keyframe{index + 1}{ext}",
    )


@router.post("/{report_id}/keyframes/{index}/send_to_drz", response_model=dict)
def send_keyframe_to_drz(
    report_id: int,
    index: int,
    body: KeyframeShareRequest,
    db: Session = Depends(get_db),
):
    """
    Send one keyframe panorama to the DRZ/IAIS photo service with a manually picked
    coordinate, and remember that coordinate on the report.

    Keyframes carry no GPS — the SLAM poses are in a local metric frame — so the
    coordinate comes from the user picking it on a map in the viewer.
    """
    reconstruction = report_crud.get_reconstruction_report(db, report_id)
    if not reconstruction:
        raise HTTPException(status_code=404, detail="Reconstruction report not found")
    if not config.DRZ_BACKEND_URL:
        raise HTTPException(status_code=503, detail="DRZ backend is not configured")

    path, filename = _resolve_keyframe(report_id, index)

    # Re-sending the same keyframe should update the existing photo, not duplicate it.
    existing = (reconstruction.keyframe_geo or {}).get(str(index), {})
    previous_photo_id = existing.get("iais_photo_id")

    success, message, photo_id = send_photo_to_iais(
        image_path=path,
        name=body.name,
        lat=body.lat,
        lon=body.lon,
        projection="panorama_360_equirectangular",
        description=body.description,
        photo_id=previous_photo_id,
    )

    if not success:
        logger.warning(f"Keyframe {index} of report {report_id} could not be sent to DRZ: {message}")
        # Reported as 200 with success=false so the dialog can show the backend's own
        # error text — that message is the main signal when debugging the integration.
        return {"success": False, "message": message, "photo_id": None}

    entry = {
        "lat": body.lat,
        "lon": body.lon,
        "name": body.name,
        "description": body.description,
        "iais_photo_id": photo_id or previous_photo_id,
        "sent_at": datetime.now(timezone.utc).isoformat(),
    }
    # Reassign instead of mutating — SQLAlchemy does not track in-place JSONB changes.
    report_crud.update_reconstruction_report(
        db, report_id,
        keyframe_geo={**(reconstruction.keyframe_geo or {}), str(index): entry},
    )

    logger.info(f"Sent keyframe {index} ({filename}) of report {report_id} to DRZ as photo {photo_id}")
    return {"success": True, "message": message, "photo_id": entry["iais_photo_id"]}
