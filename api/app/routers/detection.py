from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List
from celery import chain
import logging

import app.crud.report as report_crud
import app.crud.images as image_crud

from app import models

from app.database import get_db
from app.schemas.image import (
    DetectionCreate,
    DetectionOut,
    ImageOut,
    DetectionUpdate,
    DetectionSettings,
    DetectionIncremental,
    DetectionUniqueObjectAssign,
    DetectionObjectGroup,
    ReidInput,
    DetectionUniqueObjectsBulk,
    FireMapOut,
    DetectionShareRequest,
)

from app.services.celery_app import celery_app
from app.services.detection_geo import estimate_detection_gps
from app.services.image_processing import resolve_image_path
from app.services.drz_backend_sharing import send_geojson_poi_to_iais, send_photo_to_iais
from app.services.fire_map import build_fire_map
import app.services.events as events_service

import redis
from app.config import config
r = redis.Redis(host=config.REDIS_HOST, port=config.REDIS_PORT, db=0)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/detections", tags=["Detections"])

# Classes produced by the dedicated fire pipeline. Fire and object runs are
# dispatched separately and must not wipe each other's results, so detection
# deletion at dispatch is scoped by these class names.
FIRE_CLASSES = {"fire"}


@router.get("/", response_model=List[DetectionOut])
def get_all_detections(db: Session = Depends(get_db)):
    """
    Get all detections.
    """
    detections = image_crud.get_all_detections(db)
    return detections


@router.post("/", response_model=DetectionOut)
def create_detection(detection: DetectionCreate, db: Session = Depends(get_db)):
    """
    Create a single detection by hand — an object a detector missed.

    Always stored with manually_created=True, which keeps it out of the
    delete-before-rerun in run_detections. RGB only: thermal frames are drawn at
    a different scale to their RGB counterpart and panoramas have no usable
    footprint, so a bbox on either cannot be georeferenced with the same math.
    If the caller supplies no coord, one is estimated from the image's ground
    footprint; images that were never mapped simply get coord=None.
    """
    image = image_crud.get_full_image(db, detection.image_id)
    if not image:
        raise HTTPException(status_code=404, detail="Image not found")
    if image.thermal or image.panoramic:
        raise HTTPException(
            status_code=400,
            detail="Manual detections can only be added to RGB images",
        )

    data = detection.model_copy(update={"manually_created": True})
    if not data.coord:
        data.coord = estimate_detection_gps(db, image, data.bbox)

    created = image_crud.create_detection(db, data)

    if image.mapping_report:
        # Same announcement the worker callback makes, so other open tabs pull
        # the new row over SSE instead of waiting for a refetch.
        events_service.publish_event(
            r, image.mapping_report.report_id, events_service.EVENT_DETECTIONS_ADDED,
            data={"count": 1},
        )

    return created


@router.post("/r/{report_id}", response_model=dict)
def run_detections(report_id: int, req: DetectionSettings, db: Session = Depends(get_db)):
    """
    Queue detection tasks for a given report.
    """
    r.set(f"detection:{report_id}:progress", 0)
    r.set(f"detection:{report_id}:status", "queued")
    r.set(f"detection:{report_id}:message", "Detection task queued")

    mapping_report = report_crud.get_short_report(db, report_id).mapping_report
    if not mapping_report:
        r.delete(f"detection:{report_id}:status")
        r.delete(f"detection:{report_id}:progress")
        r.delete(f"detection:{report_id}:message")
        raise HTTPException(status_code=404, detail="Mapping report not found for the given report ID")
    images_list = image_crud.get_images_for_detection(db, mapping_report.id)
    if not images_list:
        r.delete(f"detection:{report_id}:status")
        r.delete(f"detection:{report_id}:progress")
        r.delete(f"detection:{report_id}:message")
        raise HTTPException(status_code=404, detail="No images found for the given report ID")
    
    max_splits = 0
    pipeline = "roblab_rescue"
    yolo_pipeline = "objects"
    if req.processing_mode == "medium":
        max_splits = 1
    elif req.processing_mode == "detailed":
        max_splits = 4
    elif req.processing_mode == "experimental":
        pipeline = "yolo"
    elif req.processing_mode == "fire":
        pipeline = "yolo"
        yolo_pipeline = "fire"

    # Scoped cleanup: a fire run only replaces fire detections, an object
    # (experimental) run replaces everything except them. The legacy roblab
    # modes stay authoritative for everything (they may emit "fire" too).
    if req.processing_mode == "fire":
        image_crud.delete_detections_by_class_names(db, mapping_report.id, FIRE_CLASSES)
    elif req.processing_mode == "experimental":
        image_crud.delete_detections_by_class_names(db, mapping_report.id, FIRE_CLASSES, invert=True)
    else:
        image_crud.delete_all_detections_by_mapping_report_id(db, mapping_report.id)

    detection_task = None
    if pipeline == "yolo":
        # Forward the deployment's HF token so the worker can fetch the gated
        # DINOv3 re-ID weights — a token saved on the settings page takes
        # effect on the next run, no worker restart needed.
        detection_task = celery_app.signature(
            "detection_yolo.run",
            args=[report_id, images_list],
            kwargs={
                "hf_token": config.env_vars.get("HF_TOKEN", ""),
                "pipeline": yolo_pipeline,
            },
            queue="detection_yolo",
        )
    else:
        detection_task = celery_app.signature(
            "detection.run", args=[report_id, images_list, max_splits], queue="detection"
        )
    try:
        asynch_task = detection_task.apply_async()
    except Exception as e:
        # Dispatch failed — don't leave an orphaned "queued" status behind (it has
        # no task_id, so it would otherwise look stuck forever until a restart).
        r.delete(f"detection:{report_id}:status")
        r.delete(f"detection:{report_id}:progress")
        r.delete(f"detection:{report_id}:message")
        logger.error(f"Failed to dispatch detection task for report {report_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to queue detection task")

    r.set(f"detection:{report_id}:task_id", asynch_task.id)
    #logger.info(f"Detection task {asynch_task.id} queued for report {report_id}")
    events_service.publish_event(
        r, report_id, events_service.EVENT_DETECTION_STATUS,
        status="queued", progress=0, message="Detection task queued",
    )

    return {"message": "Detection task queued", "report_id": report_id}


@router.put("/r/{report_id}", response_model=dict)
def set_detections(report_id: int, detections: dict, db: Session = Depends(get_db)):
    """
    Save detection results for a given report.
    """
    mapping_report = report_crud.get_short_report(db, report_id).mapping_report
    if not mapping_report:
        raise HTTPException(status_code=404, detail="Report not found")
    logger.info(f"Saving {len(detections.get('detections', []))} detections for report {report_id}")
    #logger.info(detections)
    #
    image_crud.save_detections(db, mapping_report.id, detections)  # adapt to your CRUD

    # New rows are now queryable — tell live SSE clients to pull them. The
    # worker keeps ownership of the detection *status* (it may still be doing
    # reID/3D localization after this PUT), so only announce the data here.
    events_service.publish_event(
        r, report_id, events_service.EVENT_DETECTIONS_ADDED,
        data={"count": len(detections.get("detections", []))},
    )

    return {"message": "Detections saved successfully", "report_id": report_id, "detections": detections}


@router.get("/r/{report_id}", response_model=List[DetectionOut])
def get_detections(report_id: int, db: Session = Depends(get_db)):
    """
    Get detections for a given report.
    """
    mapping_report = report_crud.get_short_report(db, report_id).mapping_report
    if not mapping_report:
        raise HTTPException(status_code=404, detail="Report not found")

    detections = image_crud.get_detections_by_mapping_report_id(db, mapping_report.id)
    # logger.info(f"Found {len(detections)} detections for report {report_id}")
    # logger.info(f"{detections[0]}")
    return detections

@router.post("/r/{report_id}/incremental", response_model=List[DetectionOut])
def get_detections_incremental(report_id: int, payload: DetectionIncremental, db: Session = Depends(get_db)):
    """
    Get incremental detections for a given report.
    """
    known_ids = payload.known_ids
    # logger.info(f"Fetching incremental detections for report {report_id} excluding known IDs: {known_ids}")
    mapping_report = report_crud.get_short_report(db, report_id).mapping_report
    if not mapping_report:
        raise HTTPException(status_code=404, detail="Report not found")

    detections = image_crud.get_incremental_detections(db, mapping_report.id, known_ids)
    return detections


@router.get("/r/{report_id}/status", response_model=dict)
def get_detection_status(report_id: int):
    """
    Get the current status and progress of a detection task for a given report.
    """
    try:
        status = r.get(f"detection:{report_id}:status")
        progress = r.get(f"detection:{report_id}:progress")
        message = r.get(f"detection:{report_id}:message")

        if not status and not progress:
            raise HTTPException(status_code=404, detail="No detection status found for this report")
        
        # logger.info(f"Detection status for report {report_id}: {status}, {progress}%, {message}")

        return {
            "report_id": report_id,
            "status": status.decode() if status else "unknown",
            "progress": int(progress) if progress else 0,
            "message": message.decode() if message else "unknown"
        }
    except Exception as e:
        logger.error(f"Error retrieving detection status for report {report_id}: {e}")
        raise HTTPException(status_code=404, detail="Error retrieving detection status")


@router.put("/{detection_id}", response_model=DetectionOut)
def update_detection(detection_id: int, detection: DetectionUpdate, db: Session = Depends(get_db)):
    """
    Update a detection.
    """
    try:
        updated_detection = image_crud.update_detection(db, detection_id, detection)
        return updated_detection
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    
# @router.put("/r/{report_id}/updateCoords", response_model=dict)
# def update_detections_coords(report_id: int, db: Session = Depends(get_db)):
#     """
#     Update detection coordinates for given detections.
#     """
#     mapping_report = report_crud.get_short_report(db, report_id).mapping_report
#     if not mapping_report:
#         raise HTTPException(status_code=404, detail="Report not found")
    
#     updated_count = image_crud.update_detections_coords_by_mapping_report_id(db, mapping_report.id)
#     return {"message": f"Updated coordinates for {updated_count} detections", "report_id": report_id, "updated_count": updated_count}
    
@router.delete("/{detection_id}", response_model=dict)
def delete_detection(detection_id: int, db: Session = Depends(get_db)):
    """
    Delete a detection.
    """
    try:
        image_crud.delete_detection(db, detection_id)
        return {"message": "Detection deleted successfully", "detection_id": detection_id}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    
@router.put("/r/{report_id}/batch_update", response_model=dict)
def update_detections_batch(report_id: int, data: List[DetectionUpdate], db: Session = Depends(get_db)):
    """
    Update multiple detections in a batch.
    """
    mapping_report = report_crud.get_short_report(db, report_id).mapping_report
    if not mapping_report:
        raise HTTPException(status_code=404, detail="Report not found")
    
    logger.info(f"Updating {len(data)} detections for report {report_id}")
    #logger.info(f"First detection data: {data[0] if data else 'No data'}")

    updated_count = image_crud.update_detections_batch(db, mapping_report.id, data)
    return {"message": f"Updated {updated_count} detections", "report_id": report_id, "updated_count": updated_count}

@router.put("/r/{report_id}/unique_object", response_model=dict)
def set_unique_object_id_batch(report_id: int, data: DetectionUniqueObjectAssign, db: Session = Depends(get_db)):
    """
    Assign a unique_object_id to a batch of detections in a report.
    Passing a null unique_object_id clears the assignment for the given detections.
    """
    mapping_report = report_crud.get_short_report(db, report_id).mapping_report
    if not mapping_report:
        raise HTTPException(status_code=404, detail="Report not found")

    updated_count = image_crud.set_unique_object_id_batch(
        db, mapping_report.id, data.unique_object_id, data.detection_ids
    )
    return {
        "message": f"Updated unique_object_id for {updated_count} detections",
        "report_id": report_id,
        "updated_count": updated_count,
    }

@router.get("/r/{report_id}/reid_input", response_model=ReidInput)
def get_reid_input(report_id: int, db: Session = Depends(get_db)):
    """
    Return detections (with DB ids) plus per-image georeferencing for the YOLO
    reID worker to cluster detections of the same physical object.
    """
    mapping_report = report_crud.get_short_report(db, report_id).mapping_report
    if not mapping_report:
        raise HTTPException(status_code=404, detail="Report not found")

    return image_crud.get_reid_input(db, mapping_report.id)


@router.put("/r/{report_id}/unique_objects", response_model=dict)
def assign_unique_object_clusters(
    report_id: int, data: DetectionUniqueObjectsBulk, db: Session = Depends(get_db)
):
    """
    Bulk-assign reID clusters to a report's detections. Previous assignments for
    the report are cleared first so re-runs are clean.
    """
    mapping_report = report_crud.get_short_report(db, report_id).mapping_report
    if not mapping_report:
        raise HTTPException(status_code=404, detail="Report not found")

    clusters = {int(uid): det_ids for uid, det_ids in data.clusters.items()}
    updated_count = image_crud.assign_unique_object_clusters(
        db, mapping_report.id, clusters
    )
    return {
        "message": f"Assigned {len(clusters)} objects across {updated_count} detections",
        "report_id": report_id,
        "updated_count": updated_count,
        "object_count": len(clusters),
    }


@router.get("/r/{report_id}/fire_map", response_model=FireMapOut)
def get_fire_map(
    report_id: int,
    min_confidence: float | None = Query(default=None, ge=0.0, le=1.0),
    db: Session = Depends(get_db),
):
    """
    Vector fire overlay for the map: the report's fire-class detections
    projected to GPS, smoothly merged and sliced into confidence bands
    (GeoJSON), plus per-region source-image attribution. Computed on request
    from the current detections — no caching, always in sync. min_confidence
    raises the confidence floor (detections below it are excluded).
    """
    mapping_report = report_crud.get_short_report(db, report_id).mapping_report
    if not mapping_report:
        raise HTTPException(status_code=404, detail="Report not found")

    fire_input = image_crud.get_fire_map_input(db, mapping_report.id, FIRE_CLASSES)
    return build_fire_map(fire_input, min_confidence=min_confidence)


@router.get("/r/{report_id}/objects", response_model=List[DetectionObjectGroup])
def get_detections_grouped_by_object(report_id: int, db: Session = Depends(get_db)):
    """
    Get detections for a report grouped by unique_object_id.
    Detections without an assigned object id are returned in the null group.
    """
    mapping_report = report_crud.get_short_report(db, report_id).mapping_report
    if not mapping_report:
        raise HTTPException(status_code=404, detail="Report not found")

    return image_crud.get_detections_grouped_by_object(db, mapping_report.id)

@router.post("/send_to_iais", response_model=dict)
def send_detection_to_iais(req: DetectionShareRequest, db: Session = Depends(get_db)):
    """
    Send a detection to the Iais system as a POI, optionally with its source image.

    The image is uploaded second, carrying the `poi_id` the POI service just handed back, so
    the two end up linked. A failed image upload is reported in `image_error` and does NOT
    fail the share: the POI already exists remotely and cannot be rolled back, so calling the
    whole thing a failure would invite the operator to send a duplicate.
    """
    logger.info(f"Sending detection to Iais with properties: {req.properties}")
    try:
        success, message, detail, poi_id = send_geojson_poi_to_iais(req.geometry, req.properties)
    except Exception as e:
        logger.error(f"Error sending detection to Iais: {e}")
        return {"message": "Error sending detection to Iais", "error": str(e)}

    logger.info(f"Iais response: success={success}, message={message}, detail={detail}, poi_id={poi_id}")
    if not success:
        # HTTP 200 with an `error` key is the contract the share dialog reads; a failure here
        # is a remote-system problem, not a bad request to this API.
        return {"message": message, "error": detail or message}

    result = {"message": message, "poi_id": poi_id}
    if req.attach_image and req.detection_id is not None:
        photo_id, image_error = _attach_detection_image(db, req.detection_id, poi_id, req.properties)
        result["photo_id"] = photo_id
        if image_error:
            result["image_error"] = image_error
    return result


def _attach_detection_image(db: Session, detection_id: int, poi_id: str | None, properties: dict):
    """Upload a detection's source frame to the DRZ photo service, linked to `poi_id`.

    Returns (photo_id, error_message) — never raises, because the POI it belongs to has
    already been created and the caller must still report that as a success.
    """
    detection = (
        db.query(models.Detection).filter(models.Detection.id == detection_id).first()
    )
    if not detection or not detection.image:
        return None, "Detection or its image was not found"

    image = detection.image
    path = resolve_image_path(image)
    if not path:
        return None, f"Image file is missing on the server: {image.filename}"

    coord = _photo_coord(image, detection)
    if not coord:
        # Never fall back to (0, 0) — that is "null island", and the DRZ inspector flags it
        # as a swapped/absent coordinate rather than showing an obviously wrong pin.
        return None, "No coordinate available for the image"
    lat, lon = coord

    if not poi_id:
        # The POI went through but IAIS did not tell us its id, so the photo can still be
        # uploaded — it just won't show up under the POI.
        logger.warning("No poi_id returned; uploading the photo unlinked")

    # A mapping image knows which way the camera was pointing; pass it as the photo heading.
    direction = None
    if image.mapping_data and image.mapping_data.cam_yaw is not None:
        direction = int(round(image.mapping_data.cam_yaw))

    success, message, photo_id = send_photo_to_iais(
        image_path=path,
        name=properties.get("name") or image.filename,
        lat=lat,
        lon=lon,
        projection="panorama_360_equirectangular" if image.panoramic else "normal",
        description=properties.get("description"),
        poi_id=poi_id,
        direction=direction,
    )
    if not success:
        logger.warning(f"Image for detection {detection_id} could not be attached: {message}")
        return None, message
    return photo_id, None


def _photo_coord(image, detection) -> tuple[float, float] | None:
    """(lat, lon) for the uploaded photo: the detection's own GPS, else the camera position."""
    for source in (detection.coord, image.coord):
        gps = (source or {}).get("gps") if source else None
        if gps and gps.get("lat") is not None and gps.get("lon") is not None:
            return float(gps["lat"]), float(gps["lon"])
    return None
