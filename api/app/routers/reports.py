import json
import os
import shutil
from concurrent.futures import ThreadPoolExecutor

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import List, Literal
import logging

import app.crud.report as crud
import app.crud.groups as crud_groups
import app.crud.map as map_crud
from app.database import get_db
from app.schemas.report import (
    ReportCreate,
    ReportUpdate,
    ReportOut,
    ReportDetailOut,
    ReportSmallDetailPlusOut,
    MapOutSlim
)
from app.schemas.report import (
    MappingReportCreate,
    MappingReportUpdate,
    MappingReportOut,
    ProcessingSettings,
    ColmapResultsOut,
)
from app.schemas.image import UploadSummary, VideoUploadResult, ImageUploadResult
from app.schemas.map import MapOut, MapSharingData, ThermalMapOut
from app.services.thermal_map import build_thermal_map
from app.services.celery_app import celery_app
from app.services.image_processing import process_image, check_mapping_report, UPLOAD_DIR
from app.services.camera_config_service import extract_video_metadata

import app.services.mapping.processing_manager as process_report_service
import app.services.image_describer as image_describer_service
import app.services.drz_backend_sharing as drz_service
import app.services.map_export as map_export_service
import app.services.events as events_service
from app.config import config
import redis

IMAGE_EXTENSIONS = {"jpg", "jpeg", "png"}
VIDEO_EXTENSIONS = {"mp4", "mov", "avi", "mkv", "webm", "m4v", "ts", "mts"}

router = APIRouter(prefix="/reports", tags=["Reports"])

r = redis.Redis(host=config.REDIS_HOST, port=config.REDIS_PORT, db=0)

logger = logging.getLogger(__name__)

@router.get("/", response_model=List[ReportOut])
def list_reports(db: Session = Depends(get_db)):
    return crud.get_all(db)


@router.post("/", response_model=ReportOut)
def create_report(report: ReportCreate, db: Session = Depends(get_db)):
    return crud.create(db, report)


@router.get("/{report_id}", response_model=ReportSmallDetailPlusOut)
def get_report(report_id: int, db: Session = Depends(get_db)):
    report = crud.get_basic_report(db, report_id, r)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return report


@router.put("/{report_id}", response_model=ReportOut)
def update_report(report_id: int, update: ReportUpdate, db: Session = Depends(get_db)):
    return crud.update(db, report_id, update)


@router.delete("/{report_id}")
def delete_report(report_id: int, db: Session = Depends(get_db)):
    return crud.delete(db, report_id)


# ── Unified upload ────────────────────────────────────────────────────────────

@router.post("/{report_id}/upload", response_model=UploadSummary)
def upload_files(
    report_id: int,
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
):
    """
    Auto-detecting upload endpoint. Accepts any mix of image and video files.

    - Images only  → creates/reuses a MappingReport and processes images.
    - Video only, no MappingReport exists → creates a ReconstructionReport, saves video.
    - Video + images, OR video with existing MappingReport → processes images, discards video with warning.
    - Unknown file types → per-file error in the images list.
    """
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")

    report = crud.get_short_report(db, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    def _ext(f: UploadFile) -> str:
        return (f.filename or "").rsplit(".", 1)[-1].lower()

    image_files = [f for f in files if _ext(f) in IMAGE_EXTENSIONS]
    video_files = [f for f in files if _ext(f) in VIDEO_EXTENSIONS]
    unknown_files = [f for f in files if f not in image_files and f not in video_files]

    warnings: list[str] = []
    video_result: VideoUploadResult | None = None
    image_results: list[ImageUploadResult] = []
    report_type = "unchanged"

    has_mapping = report.mapping_report is not None

    # ── Video handling ──────────────────────────────────────────────────────
    if video_files:
        video_file = video_files[0]
        if len(video_files) > 1:
            extra = ", ".join(f.filename or "" for f in video_files[1:])
            warnings.append(f"Only one video can be uploaded at a time. Extra videos ignored: {extra}")

        if image_files or has_mapping:
            reason = (
                "images were also uploaded" if image_files
                else "a mapping report already exists for this report"
            )
            msg = (
                f"Video '{video_file.filename}' was discarded: {reason}. "
                "A report cannot contain both a mapping and a reconstruction."
            )
            warnings.append(msg)
            video_result = VideoUploadResult(status="skipped", filename=video_file.filename, message=msg)
        else:
            # Save video and create/update ReconstructionReport
            report_dir = UPLOAD_DIR / str(report_id)
            report_dir.mkdir(parents=True, exist_ok=True)

            ext = os.path.splitext(video_file.filename or "")[1] or ".mp4"
            video_filename = f"video{ext}"
            video_path = report_dir / video_filename

            with video_path.open("wb") as f:
                shutil.copyfileobj(video_file.file, f)

            relative_path = os.path.join(str(report_id), video_filename)

            # Auto-create ReconstructionReport if it doesn't exist yet
            if not crud.get_reconstruction_report(db, report_id):
                crud.create_reconstruction_report(db, report_id)
            
            flight_timestamp, camera_model, video_duration = extract_video_metadata(video_path)
            crud.update_reconstruction_report(db, report_id, video_path=relative_path, flight_timestamp=flight_timestamp, camera_model=camera_model, video_duration=video_duration)

            video_result = VideoUploadResult(status="uploaded", filename=video_file.filename)
            report_type = "reconstruction_360"

    # ── Image handling ──────────────────────────────────────────────────────
    if image_files:
        mapping_report_id = check_mapping_report(report_id, db)

        def _process(file: UploadFile):
            db_local = next(get_db())
            try:
                return process_image(report_id, file, mapping_report_id, db_local)
            except Exception as e:
                db_local.rollback()
                return ImageUploadResult(status="error", filename=file.filename, error=str(e))
            finally:
                db_local.close()

        with ThreadPoolExecutor(max_workers=12) as executor:
            image_results = list(executor.map(_process, image_files))
        report_type = "mapping"

    # ── Unknown files ───────────────────────────────────────────────────────
    for f in unknown_files:
        image_results.append(
            ImageUploadResult(status="error", filename=f.filename, error="Unsupported file type")
        )

    return UploadSummary(
        report_type=report_type,
        images=image_results,
        video=video_result,
        warnings=warnings,
    )


# MappingReport endpoints
@router.post("/{report_id}/mapping_report", response_model=MappingReportOut)
def create_mapping_report(report_id: int, data: MappingReportCreate, db: Session = Depends(get_db)):
    return crud.create_mapping_report(db, report_id, data)


@router.put("/{report_id}/mapping_report", response_model=MappingReportOut)
def update_mapping_report(report_id: int, data: MappingReportUpdate, db: Session = Depends(get_db)):
    return crud.update_mapping_report(db, report_id, data)

@router.get("/{report_id}/mapping_report/maps", response_model=list[MapOut])
def get_mapping_report_maps(report_id: int, db: Session = Depends(get_db)):
    return crud.get_mapping_report_maps(db, report_id)

@router.get("/{report_id}/mapping_report/maps_slim", response_model=list[MapOutSlim])
def get_mapping_report_maps(report_id: int, db: Session = Depends(get_db)):
    return crud.get_mapping_report_maps_slim(db, report_id)

@router.get("/{report_id}/mapping_report/maps/{map_id}", response_model=MapOut)
def get_mapping_report_single_map(report_id: int, map_id: int, db: Session = Depends(get_db)):
    """Fetch one map with its elements — used by the SSE map_created handler to
    load a freshly generated map without refetching the whole maps list."""
    try:
        crud.get_mapping_report_map(db, map_id, report_id)  # ownership check
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return map_crud.get_full_map(db, map_id)

@router.get("/{report_id}/mapping_report/maps/{map_id}/download")
def download_mapping_report_map(
    report_id: int,
    map_id: int,
    format: Literal["png", "geotiff_wgs84", "geotiff_utm"] = "png",
    filename: str | None = None,
    db: Session = Depends(get_db),
):
    """Download a map as PNG or as a georeferenced GeoTIFF (WGS84 or native UTM).

    Deliberately a sync def — the rasterio write runs in FastAPI's threadpool.
    """
    try:
        map = crud.get_mapping_report_map(db, map_id, report_id)  # ownership check
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    try:
        path, media_type = map_export_service.export_map_file(map, format)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception(f"Failed to export map {map_id} as {format}")
        raise HTTPException(status_code=500, detail=f"Failed to export map: {e}")

    stem = os.path.splitext(os.path.basename(filename or map.name or ""))[0].strip()
    if not stem:
        stem = f"map_{map_id}"
    download_name = stem + map_export_service.file_extension(format)

    return FileResponse(path, media_type=media_type, filename=download_name)

@router.get("/{report_id}/mapping_report/webodm_project_id", response_model=int | None)
def get_mapping_report_webodm_project_id(report_id: int, db: Session = Depends(get_db)):
    return crud.get_mapping_report_webodm_project_id(db, report_id)


@router.get("/{report_id}/thermal_map", response_model=ThermalMapOut)
def get_thermal_map(
    report_id: int,
    t_min: float | None = Query(default=None, description="Lower temperature clip in °C"),
    t_max: float | None = Query(default=None, description="Upper temperature clip in °C"),
    db: Session = Depends(get_db),
):
    """
    Interactive temperature overlay: the report's radiometric thermal images
    merged into a max-composite temperature field per IR map, banded in 10 °C
    steps as GeoJSON polygons, optionally clipped to [t_min, t_max] (the
    gallery's temperature filters). Composites are cached on disk, so repeat
    calls with different clips are fast.
    """
    report = crud.get_short_report(db, report_id)
    if not report or not report.mapping_report:
        raise HTTPException(status_code=404, detail="Report not found")

    tm_input = map_crud.get_thermal_map_input(db, report.mapping_report.id)
    tm_input["report_id"] = report_id
    return build_thermal_map(tm_input, t_min=t_min, t_max=t_max)

@router.post("/{report_id}/process", response_model=ReportOut)
def process_report(report_id: int, processing_settings: ProcessingSettings, db: Session = Depends(get_db)):
    returnval = crud.update_process(db, report_id, "queued", 0.0)
    processing_settings_dict = processing_settings.model_dump()
    logger.warning(f"Starting processing for report {report_id} with settings: {processing_settings_dict}")
    # Persist before dispatch so GET /processing_settings is race-free for the frontend
    crud.save_processing_settings(db, report_id, processing_settings_dict)
    task = process_report_service.process_report.delay(report_id, processing_settings_dict)
    r.set(f"report:{report_id}:task_id", task.id)
    r.set(f"report:{report_id}:progress", 0)
    r.set(f"report:{report_id}:status", "queued")
    events_service.publish_event(
        r, report_id, events_service.EVENT_REPORT_STATUS, status="queued", progress=0.0
    )
    return returnval

@router.get("/{report_id}/colmap/status", response_model=dict)
def get_colmap_status(report_id: int):
    """Poll the COLMAP 3D-reconstruction status for a report.

    State lives only in Redis (colmap:{id}:*); 3D availability is also derivable
    from the on-disk reconstruction.json. Returns status 'none' when no run has
    ever been started for this report.
    """
    return events_service.read_colmap_state(r, report_id)


@router.get("/{report_id}/colmap/results", response_model=ColmapResultsOut)
def get_colmap_results(report_id: int):
    """Point-cloud URLs and summary stats of a finished COLMAP reconstruction.

    Like the status endpoint this never 404s (there is no DB row for COLMAP):
    a report without a reconstruction gets has_reconstruction=False. The .ply
    files themselves are served by the /reports_data static mount.
    """
    colmap_dir = os.path.join(str(config.UPLOAD_DIR), str(report_id), "colmap")
    summary_path = os.path.join(colmap_dir, "reconstruction.json")
    if not os.path.isfile(summary_path):
        return ColmapResultsOut(report_id=report_id, has_reconstruction=False)

    summary = {}
    try:
        with open(summary_path) as f:
            summary = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        logger.warning(f"Unreadable reconstruction.json for report {report_id}: {e}")

    sparse_url = None
    if os.path.isfile(os.path.join(colmap_dir, "sparse_aligned", "points.ply")):
        sparse_url = f"/reports_data/{report_id}/colmap/sparse_aligned/points.ply"
    dense_url = None
    if os.path.isfile(os.path.join(colmap_dir, "dense", "fused.ply")):
        dense_url = f"/reports_data/{report_id}/colmap/dense/fused.ply"

    return ColmapResultsOut(
        report_id=report_id,
        has_reconstruction=True,
        sparse_pointcloud_url=sparse_url,
        dense_pointcloud_url=dense_url,
        has_dense_pointcloud=dense_url is not None,
        reconstruction_mode=summary.get("reconstruction_mode"),
        registered_images=summary.get("registered_images"),
        total_images=summary.get("total_images"),
    )


@router.post("/{report_id}/colmap/complete", response_model=dict)
def complete_colmap(report_id: int, summary: dict = None):
    """Best-effort completion callback from the COLMAP worker.

    Tracking is Redis + on-disk only (no DB row), so this just logs the
    registration metrics for observability. The worker already set the terminal
    Redis status before calling.
    """
    logger.info(f"COLMAP reconstruction complete for report {report_id}: {summary}")
    state = events_service.read_colmap_state(r, report_id)
    events_service.publish_event(
        r,
        report_id,
        events_service.EVENT_COLMAP_STATUS,
        status=state["status"],
        progress=state["progress"],
        message=state["message"],
        data={"has_reconstruction": state["has_reconstruction"]},
    )
    return {"ok": True, "report_id": report_id}


@router.get("/{report_id}/processing_settings", response_model=dict)
def get_processing_settings(report_id: int, db: Session = Depends(get_db)):
    """Return the last-used processing settings for prefilling the process dialog.

    Returns only the keys that were actually saved ({} if never processed), so the
    frontend can tell saved values apart from schema defaults.
    """
    return crud.get_processing_settings(db, report_id)


@router.post("/{report_id}/process/stop", response_model=ReportOut)
def stop_processing(report_id: int, db: Session = Depends(get_db)):
    """Stop a currently processing report by revoking its Celery task."""
    report = crud.get_basic_report(db, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    active_states = {"queued", "preprocessing", "processing"}
    if report.status not in active_states:
        raise HTTPException(status_code=409, detail=f"Report is not being processed (status: {report.status})")

    # Revoke the Celery task if we have a task ID
    task_id = r.get(f"report:{report_id}:task_id")
    if task_id:
        celery_app.control.revoke(task_id.decode(), terminate=True, signal='SIGTERM')

    # Read current progress before cleaning up Redis keys
    current_progress = r.get(f"report:{report_id}:progress")
    progress = float(current_progress) if current_progress else 0.0

    # Update report status to cancelled
    result = crud.update_process(db, report_id, "cancelled", progress)

    # Clean up Redis keys
    r.delete(f"report:{report_id}:task_id", f"report:{report_id}:progress", f"report:{report_id}:status")

    events_service.publish_event(
        r, report_id, events_service.EVENT_REPORT_STATUS, status="cancelled", progress=progress
    )
    return result


@router.get("/{report_id}/process/", response_model=ReportOut)
def get_process_status(report_id: int, db: Session = Depends(get_db)):
    """Get the current processing status and progress of a report."""
    return crud.get_process_status(db, report_id, r)


@router.post("/{report_id}/auto_description", response_model=dict)
def start_auto_description(report_id: int, db: Session = Depends(get_db)):
    try:
        image_describer_service.start_description_process(report_id, db)
    except ValueError as e:
        return {"status": "error", "message": str(e)}
    return {"status": "started"}


@router.get("/{report_id}/auto_description", response_model=dict)
def get_auto_description(report_id: int, db: Session = Depends(get_db)):
    # Pure read: the status watchdog owns the "did the Celery task die?" check
    # that used to be inlined here (it writes the error status and publishes
    # the matching SSE event).
    status = r.get(f"description:{report_id}:status")
    progress = r.get(f"description:{report_id}:progress")

    if status and status.decode() in ("processing", "queued"):
        return {
            "report_id": report_id,
            "status": status.decode(),
            "progress": float(progress) if progress else 0.0,
            "description": ""
        }

    if status == b"error":
        return {
            "report_id": report_id,
            "status": "error",
            "progress": 100.0,
            "description": ""
        }

    report = crud.get_basic_report(db, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    if not report.auto_description:
        return {
            "report_id": report_id,
            "status": "no_description",
            "progress": 0,
            "description": ""
        }
    return {
        "report_id": report_id,
        "status": "completed",
        "progress": 100.0,
        "description": report.auto_description
    }

@router.patch("/{report_id}/move", response_model=ReportOut)
def move_report(report_id: int, group_id: int = Query(..., description="Target group ID"), db: Session = Depends(get_db)):
    """Move a report to a different group."""
    report = crud.get_basic_report(db, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    group = crud_groups.get(db, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Target group not found")

    report.group_id = group_id
    db.commit()
    db.refresh(report)
    return report


@router.post("/{report_id}/send_map", response_model=dict)
def send_map(report_id: int, payload: MapSharingData, db:Session = Depends(get_db)):
    selected_map_id = payload.map_id
    map_layer = payload.layer_name
    try: 
        map = crud.get_mapping_report_map(db, selected_map_id, report_id)
        message = drz_service.send_map_to_iais(map, map_layer, report_id)
        return {"sucess": True, "message": "successfully sent map to DRZ backend"}
    except Exception as e:
        message = "Error during upload: " + str(e)
        return {"success": False, "message": message}