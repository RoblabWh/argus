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
    ImageOut
)

from app.services.celery_app import celery_app

import redis
from app.config import REDIS_HOST, REDIS_PORT
r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/detections", tags=["Detections"])

@router.post("/{report_id}", response_model=dict)   
def run_detections(report_id: int, db: Session = Depends(get_db)):
    """
    Queue detection tasks for a given report.
    """
    mapping_report = report_crud.get_short_report(db, report_id).mapping_report
    if not mapping_report:
        raise HTTPException(status_code=404, detail="Mapping report not found for the given report ID")
    images_list = image_crud.get_images_for_detection(db, mapping_report.id)
    if not images_list:
        raise HTTPException(status_code=404, detail="No images found for the given report ID")
    
    logger.info(f"Queueing detection task for report {report_id} with {len(images_list)} images")
    logger.info(f"{images_list}")   
    r.set(f"detection:{report_id}:progress", 0)
    r.set(f"detection:{report_id}:status", "queued")
    r.set(f"detection:{report_id}:message", "Detection task queued")

    detection_task = celery_app.signature(
        "detection.run", args=[report_id, images_list], queue="detection"
    )
    detection_task.apply_async()

    return {"message": "Detection task queued", "report_id": report_id}


@router.put("/{report_id}", response_model=dict)
def set_detections(report_id: int, detections: dict, db: Session = Depends(get_db)):
    """
    Save detection results for a given report.
    """
    mapping_report = report_crud.get_short_report(db, report_id).mapping_report
    if not mapping_report:
        raise HTTPException(status_code=404, detail="Report not found")

    image_crud.save_detections(db, mapping_report.id, detections)  # adapt to your CRUD
    r.set(f"detection:{report_id}:status", "finished")
    r.set(f"detection:{report_id}:progress", 100)
    logger.info(f"{len(detections.get('detections', []))} Detections saved for report {report_id}")

    return {"message": "Detections saved successfully", "report_id": report_id, "detections": detections}


@router.get("/{report_id}", response_model=List[DetectionOut])
def get_detections(report_id: int, db: Session = Depends(get_db)):
    """
    Get detections for a given report.
    """
    mapping_report = report_crud.get_short_report(db, report_id).mapping_report
    if not mapping_report:
        raise HTTPException(status_code=404, detail="Report not found")

    detections = image_crud.get_detections_by_mapping_report_id(db, mapping_report.id)
    logger.info(f"Found {len(detections)} detections for report {report_id}")
    logger.info(f"{detections[0]}")
    return detections

@router.get("/", response_model=List[DetectionOut])
def get_all_detections(db: Session = Depends(get_db)):
    """
    Get all detections.
    """
    detections = image_crud.get_all_detections(db)
    return detections

