from sqlalchemy.orm import Session, joinedload, selectinload, aliased
from sqlalchemy import select, func, case
from datetime import datetime
import redis

from app import models
from app.schemas.report import ReportCreate, ReportUpdate
from app.schemas.report import MappingReportCreate, MappingReportUpdate
from app.schemas.map import MapOutSlim
from app.services.cleanup import cleanup_report_folder

def get_all(db: Session):
    return db.query(models.Report).all()


def get_full_report(db: Session, report_id: int, r: redis.Redis = None):
    if r:
        try:
            get_process_status(db, report_id, r)
        except Exception as e:
            print(f"Error getting process status: {e}")
            return None

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

def get_basic_report(db: Session, report_id: int, r: redis.Redis = None):
    if r:
        try:
            get_process_status(db, report_id, r)
        except Exception as e:
            print(f"Error getting process status: {e}")
            return None

    return (
        db.query(models.Report)
        .options(                
            selectinload(models.Report.mapping_report) #todo seperate  for maps
                .selectinload(models.MappingReport.maps)
                .selectinload(models.Map.map_elements),
                
            selectinload(models.Report.mapping_report)
                .selectinload(models.MappingReport.weather),
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



def get_summaries(db: Session, group_id: int):
    """
    Returns lightweight report summary rows for a specific group_id.
    Counts are aggregated per mapping_report for each report.
    """

    mr = aliased(models.MappingReport)
    img = aliased(models.Image)
    det = aliased(models.Detection)

    stmt = (
        select(
            models.Report.report_id,
            models.Report.title,
            models.Report.description,
            models.Report.type,
            models.Report.status,
            models.Report.created_at,
            mr.flight_timestamp,
            mr.coord,

            # Total images
            func.count(func.nullif(img.id, None)).label("image_count"),

            # Thermal image count
            func.count(
                func.nullif(
                    case((img.thermal == True, img.id)),
                    None
                )
            ).label("thermal_count"),

            # Pano image count
            func.count(
                func.nullif(
                    case((img.panoramic == True, img.id)),
                    None
                )
            ).label("pano_count"),
            func.count(func.nullif(det.id, None)).label("detection_count"),

        )
        .join(mr, models.Report.mapping_report, isouter=True)
        .join(img, mr.images, isouter=True)
        .join(det, img.detections, isouter=True)
        .where(models.Report.group_id == group_id) 
        .group_by(models.Report.report_id, mr.flight_timestamp, mr.coord)
        .order_by(models.Report.created_at.desc())
    )

    summaries = {r.report_id: {
        "report_id": r.report_id,
        "title": r.title,
        "description": r.description,
        "type": r.type,
        "status": r.status,
        "created_at": r.created_at,
        "flight_timestamp": r.flight_timestamp,
        "coord": r.coord,
        "image_count": r.image_count or 0,
        "thermal_count": r.thermal_count or 0,
        "pano_count": r.pano_count or 0,
        "detection_count": r.detection_count or 0,
        "maps": []  # placeholder
    } for r in db.execute(stmt).all()}

    if not summaries:
        return []

    map_results = (
        db.query(models.Map)
        .join(models.MappingReport)
        .join(models.Report)
        .filter(models.Report.report_id.in_(summaries.keys()))
        .options(joinedload(models.Map.mapping_report))
        .all()
    )

    for mp in map_results:
        # Attach MapOutSlim
        slim = MapOutSlim.from_orm(mp)
        summaries[mp.mapping_report.report_id]["maps"].append(slim)

    return list(summaries.values())


# Mapping Report Handlers

def create_mapping_report(db: Session, report_id: int):
    existing = db.query(models.MappingReport).filter(models.MappingReport.report_id == report_id).first()
    if existing:
        raise ValueError("Mapping report already exists for this report")
    
    update_report_type(db, report_id, "mapping")

    mapping_report = models.MappingReport(report_id=report_id)
    db.add(mapping_report)
    db.commit()
    db.refresh(mapping_report)
    return mapping_report

def update_report_type(db: Session, report_id: int, new_type: str):
    report = db.query(models.Report).filter(models.Report.report_id == report_id).first()
    if not report:
        raise ValueError("Report not found")
    
    report.type = new_type
    db.commit()
    db.refresh(report)
    return report


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
    return mapping_report.webodm_project_id

def get_mapping_report_maps_slim(db: Session, report_id: int):
    mapping_report = db.query(models.MappingReport).filter(models.MappingReport.report_id == report_id).first()
    if not mapping_report:
        return []

    maps = db.query(models.Map).filter(models.Map.mapping_report_id == mapping_report.id).all()
    return maps

def get_mapping_report_maps(db: Session, report_id: int):
    mapping_report = db.query(models.MappingReport).filter(models.MappingReport.report_id == report_id).first()
    if not mapping_report:
        return []

    maps = db.query(models.Map).options(joinedload(models.Map.map_elements)).filter(models.Map.mapping_report_id == mapping_report.id).all()
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


def set_auto_description(db: Session, report_id: int, description: str):
    report = db.query(models.Report).filter(models.Report.report_id == report_id).first()
    if not report:
        raise ValueError("Report not found")

    report.auto_description = description
    db.commit()
    db.refresh(report)
    return report.auto_description
