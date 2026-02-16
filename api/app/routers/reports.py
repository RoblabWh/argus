from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

import app.crud.report as crud
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
    ProcessingSettings
)

from app.schemas.map import MapOut, MapSharingData
from app.services.celery_app import celery_app, task_is_really_active

import app.services.mapping.processing_manager as process_report_service
import app.services.image_describer as image_describer_service
import app.services.drz_backend_sharing as drz_service
from app.config import config
import redis

router = APIRouter(prefix="/reports", tags=["Reports"])

r = redis.Redis(host=config.REDIS_HOST, port=config.REDIS_PORT, db=0)

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

@router.get("/{report_id}/mapping_report/webodm_project_id", response_model=int | None)
def get_mapping_report_webodm_project_id(report_id: int, db: Session = Depends(get_db)):
    return crud.get_mapping_report_webodm_project_id(db, report_id)

@router.post("/{report_id}/process", response_model=ReportOut)
def process_report(report_id: int, processing_settings: ProcessingSettings, db: Session = Depends(get_db)):
    returnval = crud.update_process(db, report_id, "queued", 0.0)
    settings_json = processing_settings.json()
    processing_settings_dict = processing_settings.dict()
    # print(f"Starting processing for report {report_id} with settings: {processing_settings}")
    # print(f"Settings JSON: {settings_json}")
    task = process_report_service.process_report.delay(report_id, processing_settings_dict)
    r.set(f"report:{report_id}:task_id", task.id)
    r.set(f"report:{report_id}:progress", 0)
    return returnval

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
    r.delete(f"report:{report_id}:task_id", f"report:{report_id}:progress")

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
    task_id = r.get(f"description:{report_id}:task_id")
    status = r.get(f"description:{report_id}:status")
    progress = r.get(f"description:{report_id}:progress")
    
    if status and status.decode() in ("processing", "queued"):
        if task_id:
            if not task_is_really_active(task_id.decode()):
                status = b"error"
                progress = 100.0
                r.set(f"description:{report_id}:status", status)
                r.set(f"description:{report_id}:progress", progress)
            
            return {
                "report_id": report_id,
                "status": status.decode() if status else "unknown",
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