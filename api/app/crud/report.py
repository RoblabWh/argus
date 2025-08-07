from sqlalchemy.orm import Session, joinedload, selectinload
from datetime import datetime
import redis

from app import models
from app.schemas.report import ReportCreate, ReportUpdate
from app.schemas.report import MappingReportCreate, MappingReportUpdate
from app.services.cleanup import cleanup_report_folder

def get_all(db: Session):
    return db.query(models.Report).all()


def get_full_report(db: Session, report_id: int, r: redis.Redis = None):
    if r:
        get_process_status(db, report_id, r)

    return (
        db.query(models.Report)
        .options(
            selectinload(models.Report.mapping_report)
                .selectinload(models.MappingReport.images)
                .selectinload(models.Image.mapping_data),

            selectinload(models.Report.mapping_report)
                .selectinload(models.MappingReport.images)
                .selectinload(models.Image.thermal_data),
                
            selectinload(models.Report.mapping_report)
                .selectinload(models.MappingReport.images)
                .selectinload(models.Image.detections),
                
            selectinload(models.Report.mapping_report)
                .selectinload(models.MappingReport.maps)
                .selectinload(models.Map.map_elements),
                
            selectinload(models.Report.mapping_report)
                .selectinload(models.MappingReport.weather),
        )
        .filter(models.Report.report_id == report_id)
        .first()
    )

def get_short_report(db: Session, report_id: int):
    return (
        db.query(models.Report)
        .options(
            joinedload(models.Report.mapping_report),
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
    try:
        cleanup_report_folder(report_id)
    except Exception as e:
        print(f"Error cleaning up report folder: {e}")
        return {"error": str(e)}
    if report:
        db.delete(report)
        db.commit()
    return {"message": f"Report {report_id} deleted"}


# Mapping Report Handlers

def create_mapping_report(db: Session, report_id: int):
    existing = db.query(models.MappingReport).filter(models.MappingReport.report_id == report_id).first()
    if existing:
        raise ValueError("Mapping report already exists for this report")

    mapping_report = models.MappingReport(report_id=report_id)
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

def set_webODM_project_id(db: Session, mapping_report_id: int, project_id: str):
    mapping_report = db.query(models.MappingReport).filter(models.MappingReport.id == mapping_report_id).first()
    if not mapping_report:
        raise ValueError("Mapping report not found")

    mapping_report.webodm_project_id = project_id
    db.commit()
    db.refresh(mapping_report)
    return mapping_report

def get_mapping_report_maps(db: Session, report_id: int):
    mapping_report = db.query(models.MappingReport).filter(models.MappingReport.report_id == report_id).first()
    if not mapping_report:
        return []

    maps = db.query(models.Map).filter(models.Map.mapping_report_id == mapping_report.id).all()
    return maps

def get_mapping_report_webodm_project_id(db: Session, report_id: int):
    mapping_report = db.query(models.MappingReport).filter(models.MappingReport.report_id == report_id).first()
    if not mapping_report:
        return None

    return mapping_report.webodm_project_id



def update_process(db: Session, report_id: int, status: str = "queued", progress: float = 0):
    """Sets the (initial) processing status and progress of a report."""
    report = db.query(models.Report).filter(models.Report.report_id == report_id).first()
    if not report:
        raise ValueError("Report not found")

    # Update processing status
    report.status = status
    report.progress = progress
    db.commit()
    #print(f"Report {report_id} status updated to {status} with progress {progress}")

    return report



def get_process_status(db: Session, report_id: int, r: redis.Redis):
    
    #first check the progress and status saved in postgresql
    report = db.query(models.Report).filter(models.Report.report_id == report_id).first()
    if not report:
        raise ValueError("Report not found")

    #if status is preprocessing or processing check redis if the task is still going or crahed
    status = report.status

    if status in ["preprocessing", "processing", "queued"]:
        # check redis for the task status
        try:
            task_id = r.get(f"report:{report_id}:task_id")
            if not task_id:
                # no task found, set status to failed
                report.status = "failed"
                report.progress = 0.0
                db.commit()
                return {"status": "failed", "progress": 0.0}
            # print(f"Task ID for report {report_id}: {task_id.decode('utf-8')}")
            task_status = r.get(f"report:{report_id}:progress")
            # print(f"Task status for report {report_id}: {task_status}")
            if task_status is None:
                # no progress found, set status to failed
                report.status = "failed"
                report.progress = 0.0
                db.commit()
                return {"status": "failed", "progress": 0.0}
            elif float(task_status) >= 100.0:
                if status == "preprocessing":
                    report.status = "processing"
                    report.progress = 0.0
                else:
                    report.status = "completed"
                    report.progress = 100.0
                db.commit()
                return report
            elif float(task_status) < 0.0:
                report.status = "failed"
                report.progress = 0.0
                db.commit()
                return {"status": "failed", "progress": 0.0}
            # elif float(task_status) == 0.0:
            #     report.status = "failed"
            #     report.progress = float(task_status)
            #     db.commit()
            #     return {"status": "failed", "progress": float(task_status)}
        except redis.RedisError as e:
            print(f"Redis error: {e}")
            # if redis is not available, set status to failed
            report.status = "unprocessed"
            report.progress = 0.0
            db.commit()

    return report
