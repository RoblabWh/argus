from sqlalchemy.orm import Session, joinedload
# from app.models import group as models
# from app.models import report as report_models

from app import models
from app.schemas.group import GroupCreate, GroupUpdate
from app.schemas.report import ReportDetailOut


def get_all(db: Session):
    return db.query(models.Group).all()


def create(db: Session, group: GroupCreate):
    db_group = models.Group(**group.dict())
    db.add(db_group)
    db.commit()
    db.refresh(db_group)
    return db_group


def get(db: Session, group_id: int):
    return (
        db.query(models.Group)
        .options(
            joinedload(models.Group.reports)  # only loads basic reports
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
