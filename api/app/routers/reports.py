from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

import app.crud.report as crud
from app.database import get_db
from app.schemas.report import (
    ReportCreate, ReportUpdate, ReportOut, ReportDetailOut
)
from app.schemas.report import MappingReportCreate, MappingReportUpdate, MappingReportOut

router = APIRouter(prefix="/reports", tags=["Reports"])


@router.get("/", response_model=List[ReportOut])
def list_reports(db: Session = Depends(get_db)):
    return crud.get_all(db)


@router.post("/", response_model=ReportOut)
def create_report(report: ReportCreate, db: Session = Depends(get_db)):
    return crud.create(db, report)


@router.get("/{report_id}", response_model=ReportDetailOut)
def get_report(report_id: int, db: Session = Depends(get_db)):
    report = crud.get_full_report(db, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return report


@router.put("/{report_id}", response_model=ReportOut)
def update_report(report_id: int, update: ReportUpdate, db: Session = Depends(get_db)):
    return crud.update(db, report_id, update)


@router.delete("/{report_id}")
def delete_report(report_id: int, db: Session = Depends(get_db)):
    # TODO: Add filesystem cleanup logic
    return crud.delete(db, report_id)


# MappingReport endpoints
@router.post("/{report_id}/mapping_report", response_model=MappingReportOut)
def create_mapping_report(report_id: int, data: MappingReportCreate, db: Session = Depends(get_db)):
    return crud.create_mapping_report(db, report_id, data)


@router.put("/{report_id}/mapping_report", response_model=MappingReportOut)
def update_mapping_report(report_id: int, data: MappingReportUpdate, db: Session = Depends(get_db)):
    return crud.update_mapping_report(db, report_id, data)
