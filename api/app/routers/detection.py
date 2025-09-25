from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from celery import chain
import logging

import app.crud.report as report_crud
import app.crud.images as image_crud

from app.database import get_db
from app.schemas.image import (
    DetectionCreate,
    DetectionOut,
    ImageOut,
    DetectionUpdate,
    DetectionSettings
)

from app.services.celery_app import celery_app
from app.services.drz_backend_sharing import send_geojson_poi_to_iais

import redis
from app.config import config
r = redis.Redis(host=config.REDIS_HOST, port=config.REDIS_PORT, db=0)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/detections", tags=["Detections"])


@router.get("/", response_model=List[DetectionOut])
def get_all_detections(db: Session = Depends(get_db)):
    """
    Get all detections.
    """
    detections = image_crud.get_all_detections(db)
    return detections

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
    if req.processing_mode == "medium":
        max_splits = 1
    elif req.processing_mode == "detailed":
        max_splits = 4

    detection_task = celery_app.signature(
        "detection.run", args=[report_id, images_list, max_splits], queue="detection"
    )
    asynch_task = detection_task.apply_async()

    r.set(f"detection:{report_id}:task_id", asynch_task.id)
    #logger.info(f"Detection task {asynch_task.id} queued for report {report_id}")

    return {"message": "Detection task queued", "report_id": report_id}


@router.put("/r/{report_id}", response_model=dict)
def set_detections(report_id: int, detections: dict, db: Session = Depends(get_db)):
    """
    Save detection results for a given report.
    """
    mapping_report = report_crud.get_short_report(db, report_id).mapping_report
    if not mapping_report:
        raise HTTPException(status_code=404, detail="Report not found")
    image_crud.delete_all_detections_by_mapping_report_id(db, mapping_report.id)
    image_crud.save_detections(db, mapping_report.id, detections)  # adapt to your CRUD
    r.set(f"detection:{report_id}:status", "finished")
    r.set(f"detection:{report_id}:progress", 100)
    r.set(f"detection:{report_id}:message", "Detections saved successfully")
    # logger.info(f"{len(detections.get('detections', []))} Detections saved for report {report_id}")

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
    logger.info(f"First detection data: {data[0] if data else 'No data'}")

    updated_count = image_crud.update_detections_batch(db, mapping_report.id, data)
    return {"message": f"Updated {updated_count} detections", "report_id": report_id, "updated_count": updated_count}

@router.post("/send_to_iais", response_model=dict)
def send_detection_to_iais(geometry: dict, properties: dict, db: Session = Depends(get_db)):
    """
    Send a detection to Iais system.
    """
    logger.info(f"Sending detection to Iais with properties: {properties}")
    logger.info(f"Geometry: {geometry}")
    try:
        iais_response = send_geojson_poi_to_iais(geometry, properties)
        logger.info(f"Iais response: {iais_response}")
        return {"message": "Detection sent to Iais successfully", "iais_response": iais_response}
    except Exception as e:
        logger.error(f"Error sending detection to Iais: {e}")
        return {"message": "Error sending detection to Iais", "error": str(e)}