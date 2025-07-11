from sqlalchemy.orm import Session, joinedload
# from app.models import group as models
# from app.models import report as report_models

from app import models
from app.schemas.group import GroupCreate, GroupUpdate
from app.schemas.report import ReportDetailOut, ReportSmallDetailOut
from datetime import datetime


def get_all(db: Session):
    return db.query(models.Group).all()

def get_all_with_report_metadata(db: Session):
    # Fetch all groups with their associated reports and their mapping_reports
    print("Fetching all groups with report metadata")
    return (
        db.query(models.Group)
        .options(
            joinedload(models.Group.reports)  

            # .joinedload(models.Group.reports)
            # .joinedload(models.Report.pano_report)
        )
        .all()
    )


def create(db: Session, group: GroupCreate):
    datetime_now = datetime.utcnow()  # Assuming you have a datetime field in your Group model
    db_group = models.Group(**group.dict(), created_at=datetime_now)
    db.add(db_group)
    db.commit()
    db.refresh(db_group)
    return db_group


def get(db: Session, group_id: int):
    return (
        db.query(models.Group)
        .options(
            joinedload(models.Group.reports)  # only loads basic reports
            .joinedload(models.Report.mapping_report)
        )
        .filter(models.Group.id == group_id)
        .first()
    )


def update(db: Session, group_id: int, update_data: GroupUpdate):
    db_group = db.query(models.Group).filter(models.Group.id == group_id).first()
    if not db_group:
        return None
    for field, value in update_data.dict(exclude_unset=True).items():
        setattr(db_group, field, value)
    db.commit()
    db.refresh(db_group)
    return db_group


def delete(db: Session, group_id: int):
    db_group = db.query(models.Group).filter(models.Group.id == group_id).first()
    if db_group:
        # Disassociate all reports in the group
        db.query(models.Report).filter(models.Report.group_id == group_id).update({models.Report.group_id: None})

        db.delete(db_group)
        db.commit()
    return {"message": "Deleted"}


def get_reports_by_group_full(db: Session, group_id: int):
    return (
        db.query(models.Group)
        .options(
            joinedload(models.Group.reports)
            .joinedload(models.Report.mapping_report)
            .joinedload(models.MappingReport.images)
            .joinedload(models.Image.mapping_data),
            
            # joinedload(models.Group.reports)
            # .joinedload(models.Report.mapping_report)
            # .joinedload(models.MappingReport.images)
            # .joinedload(models.Image.thermal_data),
            
            joinedload(models.Group.reports)
            .joinedload(models.Report.mapping_report)
            .joinedload(models.MappingReport.images)
            .joinedload(models.Image.detections),

            joinedload(models.Group.reports)
            .joinedload(models.Report.mapping_report)
            .joinedload(models.MappingReport.maps)
            .joinedload(models.Map.map_elements),

            joinedload(models.Group.reports)
            .joinedload(models.Report.mapping_report)
            .joinedload(models.MappingReport.weather)
        )
        .filter(models.Group.id == group_id)
        .first()
    )
