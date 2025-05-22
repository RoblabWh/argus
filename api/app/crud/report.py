from sqlalchemy.orm import Session, joinedload
from datetime import datetime

from app import models
from app.schemas.report import ReportCreate, ReportUpdate
from app.schemas.report import MappingReportCreate, MappingReportUpdate


def get_all(db: Session):
    return db.query(models.Report).all()


def get_full_report(db: Session, report_id: int):
    return (
        db.query(models.Report)
        .options(
            joinedload(models.Report.mapping_report)
            .joinedload(models.MappingReport.images)
            .joinedload(models.Image.mapping_data),

            # joinedload(models.Report.mapping_report)
            # .joinedload(models.MappingReport.images)
            # .joinedload(models.Image.thermal_data),

            joinedload(models.Report.mapping_report)
            .joinedload(models.MappingReport.images)
            .joinedload(models.Image.detections),

            joinedload(models.Report.mapping_report)
            .joinedload(models.MappingReport.maps)
            .joinedload(models.Map.map_elements),

            joinedload(models.Report.mapping_report)
            .joinedload(models.MappingReport.weather),
            
            #joinedload(models.Report.pano_report)  # Future use
        )
        .filter(models.Report.report_id == report_id)
        .first()
    )


def create(db: Session, data: ReportCreate):
    new_report = models.Report(
        **data.dict(),
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    db.add(new_report)
    db.commit()
    db.refresh(new_report)
    return new_report


def update(db: Session, report_id: int, update_data: ReportUpdate):
    report = db.query(models.Report).filter(models.Report.report_id == report_id).first()
    if not report:
        raise ValueError("Report not found")

    for key, value in update_data.dict(exclude_unset=True).items():
        setattr(report, key, value)

    report.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(report)
    return report


def delete(db: Session, report_id: int):
    report = db.query(models.Report).filter(models.Report.report_id == report_id).first()
    if report:
        db.delete(report)
        db.commit()
    delete_report_files(report_id)
    return {"message": f"Report {report_id} deleted"}


# Mapping Report Handlers

def create_mapping_report(db: Session, report_id: int, data: MappingReportCreate):
    existing = db.query(models.MappingReport).filter(models.MappingReport.report_id == report_id).first()
    if existing:
        raise ValueError("Mapping report already exists for this report")

    mapping_report = models.MappingReport(**data.dict())
    db.add(mapping_report)
    db.commit()
    db.refresh(mapping_report)
    return mapping_report


def update_mapping_report(db: Session, report_id: int, data: MappingReportUpdate):
    mapping = db.query(models.MappingReport).filter(models.MappingReport.report_id == report_id).first()
    if not mapping:
        raise ValueError("Mapping report not found")

    for key, value in data.dict(exclude_unset=True).items():
        setattr(mapping, key, value)

    db.commit()
    db.refresh(mapping)
    return mapping


def delete_report_files(report_id: int):
    # TODO: Implement file deletion logic
    pass