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

import redis
from app.config import REDIS_HOST, REDIS_PORT
r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0)

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