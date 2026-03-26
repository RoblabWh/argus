import os
import logging
from typing import Optional

import redis
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel
from sqlalchemy.orm import Session

import app.crud.report as report_crud
from app.database import get_db
from app.config import config
from app.schemas.report import ReportCreate, ReportOut, ReconstructionSettings, ReconstructionReportOut
from app.services.celery_app import celery_app

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/reconstruction", tags=["Reconstruction"])

r = redis.Redis(host=config.REDIS_HOST, port=config.REDIS_PORT, db=0)

# Paths as seen from inside each container (same shared volume, different mount points)
API_REPORTS_PATH = "/api/reports_data"
STELLA_REPORTS_PATH = "/data/reports"


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


# ── Video upload ──────────────────────────────────────────────────────────────

@router.post("/{report_id}/upload", response_model=ReconstructionReportOut)
def upload_video(report_id: int, file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Upload a 360° video for the given report."""
    reconstruction = report_crud.get_reconstruction_report(db, report_id)
    if not reconstruction:
        raise HTTPException(status_code=404, detail="Reconstruction report not found")

    report_dir = os.path.join(API_REPORTS_PATH, str(report_id))
    os.makedirs(report_dir, exist_ok=True)

    # Preserve original extension; fallback to .mp4
    ext = os.path.splitext(file.filename or "")[1] or ".mp4"
    video_filename = f"video{ext}"
    video_path = os.path.join(report_dir, video_filename)

    with open(video_path, "wb") as f:
        f.write(file.file.read())

    # Store relative path (relative to reports_data/)
    relative_path = os.path.join(str(report_id), video_filename)
    reconstruction = report_crud.update_reconstruction_report(
        db, report_id, video_path=relative_path
    )
    return reconstruction


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

    report_crud.update_reconstruction_report(db, report_id, processing_settings=settings.model_dump())
    return report_crud.update_process(db, report_id, "queued", 0.0)


# ── Status polling ────────────────────────────────────────────────────────────

@router.get("/{report_id}/status", response_model=dict)
def get_reconstruction_status(report_id: int):
    """Poll the current status and progress from Redis."""
    status = r.get(f"reconstruction:{report_id}:status")
    progress = r.get(f"reconstruction:{report_id}:progress")
    message = r.get(f"reconstruction:{report_id}:message")

    if not status and not progress:
        raise HTTPException(status_code=404, detail="No reconstruction status found for this report")

    return {
        "report_id": report_id,
        "status": status.decode() if status else "unknown",
        "progress": int(progress) if progress else 0,
        "message": message.decode() if message else "",
    }


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
    keyframes_dir = os.path.join(results_dir, "keyframes")
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
    if os.path.isdir(keyframes_dir):
        #ToDo fix: images are saved as image0 image1 image10 image101 ... we need to strip the image prefix and sort by the number, not lexicographically
        image_files = sorted([
            f for f in os.listdir(keyframes_dir)
            if f.lower().endswith((".jpg", ".jpeg", ".png"))
        ], key=lambda x: int(os.path.splitext(x)[0].replace("image", "")))
        for idx, filename in enumerate(image_files):
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
    }
    return result
