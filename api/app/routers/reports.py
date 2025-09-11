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

from app.schemas.map import MapOut

import app.services.mapping.processing_manager as process_report_service
import app.services.image_describer as image_describer_service
from app.config import REDIS_HOST, REDIS_PORT
import redis

router = APIRouter(prefix="/reports", tags=["Reports"])

r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0)

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
    
    if status == b"processing" or status == b"queued":
        progress = r.get(f"description:{report_id}:progress")
        return {
            "report_id": report_id,
            "status": status.decode() if status else "unknown",
            "progress": float(progress) if progress else 0.0,
            "description": ""
        }
    elif status == b"error":
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