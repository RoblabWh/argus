from sqlalchemy.orm import Session, joinedload, selectinload, aliased
from sqlalchemy import select, func, case
from datetime import datetime, timezone
import redis
import logging

from app import models
from app.schemas.report import ReportCreate, ReportUpdate
from app.schemas.report import MappingReportCreate, MappingReportUpdate
from app.schemas.map import MapOutSlim
from app.services.cleanup import cleanup_report_folder

logger = logging.getLogger(__name__)

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
        **data.model_dump(),
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )
    db.add(new_report)
    db.commit()
    db.refresh(new_report)
    return new_report


def update(db: Session, report_id: int, update_data: ReportUpdate):
    report = db.query(models.Report).filter(models.Report.report_id == report_id).first()
    if not report:
        raise ValueError("Report not found")

    for key, value in update_data.model_dump(exclude_unset=True).items():
        setattr(report, key, value)

    report.updated_at = datetime.now(timezone.utc)
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
        slim = MapOutSlim.model_validate(mp)
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

    for key, value in data.model_dump(exclude_unset=True).items():
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

    return report



def read_process_status(db: Session, report_id: int, r: redis.Redis):
    """Pure read of a report's processing state: DB status/progress with the
    live Redis progress overlaid.

    The overlay mutates the ORM object in memory only and is never committed —
    the session is discarded (rolled back) when the request/caller closes it.
    Status reconciliation (crashed/lost tasks) lives in
    reconcile_report_status, driven by the status watchdog.
    """
    report = db.query(models.Report).filter(models.Report.report_id == report_id).first()
    if not report:
        raise ValueError("Report not found")

    if report.status in ["preprocessing", "processing", "queued"]:
        # Reconstruction reports use a separate Redis namespace managed by the
        # Stella worker (report:{id}:* keys are never set for them).
        progress_key = (
            f"reconstruction:{report_id}:progress"
            if report.type == "reconstruction_360"
            else f"report:{report_id}:progress"
        )
        try:
            progress_raw = r.get(progress_key)
            if progress_raw is not None:
                live_progress = float(progress_raw)
                if 0.0 <= live_progress <= 100.0:
                    report.progress = live_progress
        except redis.RedisError as e:
            print(f"Redis error reading progress for report {report_id}: {e}")

    return report


def get_process_status(db: Session, report_id: int, r: redis.Redis):
    """Backwards-compatible alias — now a pure read (no DB writes)."""
    return read_process_status(db, report_id, r)


def reconcile_report_status(db: Session, report_id: int, r: redis.Redis) -> bool:
    """Detect crashed/lost/finished mapping tasks and fix the DB status.

    This is the write-side logic that used to run inside the polling GET —
    it now runs from the status watchdog so failure detection no longer
    depends on someone having the report page open. Returns True when the
    DB was changed (the caller publishes the matching event).
    """
    report = db.query(models.Report).filter(models.Report.report_id == report_id).first()
    if not report or report.status not in ["preprocessing", "processing", "queued"]:
        return False

    # Reconstruction reports: the Stella worker owns the reconstruction:{id}:*
    # Redis keys and finalises via POST /reconstruction/{id}/complete. The
    # mapping liveness check below would instantly mark them failed
    # (report:{id}:task_id is never set), so instead sync the DB status from
    # the worker's Redis status — this write-back used to happen inside the
    # reconstruction status polling GET.
    if report.type == "reconstruction_360":
        try:
            status_raw = r.get(f"reconstruction:{report_id}:status")
            progress_raw = r.get(f"reconstruction:{report_id}:progress")
        except redis.RedisError as e:
            print(f"Redis error while reconciling reconstruction report {report_id}: {e}")
            return False
        worker_status = status_raw.decode() if status_raw else None
        worker_progress = float(progress_raw) if progress_raw else 0.0
        if worker_status == "error":
            report.status = "failed"
            report.progress = 0.0
            db.commit()
            return True
        if worker_status == "completed" and report.status != "completed":
            # Normally set by the /complete callback — safety net for a lost callback.
            report.status = "completed"
            report.progress = 100.0
            db.commit()
            return True
        if worker_status in ("preprocessing", "processing") and report.status != worker_status:
            report.status = worker_status
            report.progress = worker_progress
            db.commit()
            return True
        return False

    try:
        task_id = r.get(f"report:{report_id}:task_id")
        progress_raw = r.get(f"report:{report_id}:progress")
    except redis.RedisError as e:
        print(f"Redis error while reconciling report {report_id}: {e}")
        return False

    if not task_id or progress_raw is None:
        report.status = "failed"
        report.progress = 0.0
        db.commit()
        return True

    progress = float(progress_raw)
    if progress >= 100.0:
        if report.status == "preprocessing":
            report.status = "processing"
            report.progress = 0.0
            # Reset the live key too, otherwise the next reconcile tick would
            # still see 100 and mark the report completed prematurely.
            r.set(f"report:{report_id}:progress", 0)
        else:
            report.status = "completed"
            report.progress = 100.0
        db.commit()
        return True
    if progress < 0.0:
        report.status = "failed"
        report.progress = 0.0
        db.commit()
        return True

    return False


def set_auto_description(db: Session, report_id: int, description: str):
    report = db.query(models.Report).filter(models.Report.report_id == report_id).first()
    if not report:
        raise ValueError("Report not found")

    report.auto_description = description
    db.commit()
    db.refresh(report)
    return report.auto_description


def save_processing_settings(db: Session, report_id: int, settings: dict):
    mapping = db.query(models.MappingReport).filter(
        models.MappingReport.report_id == report_id
    ).first()
    if mapping:
        mapping.processing_settings = settings
        db.commit()


def get_processing_settings(db: Session, report_id: int) -> dict:
    mapping = db.query(models.MappingReport).filter(
        models.MappingReport.report_id == report_id
    ).first()
    return mapping.processing_settings or {} if mapping else {}


def create_reconstruction_report(db: Session, report_id: int):
    existing = db.query(models.ReconstructionReport).filter(
        models.ReconstructionReport.report_id == report_id
    ).first()
    if existing:
        raise ValueError("Reconstruction report already exists for this report")

    update_report_type(db, report_id, "reconstruction_360")

    reconstruction = models.ReconstructionReport(report_id=report_id)
    db.add(reconstruction)
    db.commit()
    db.refresh(reconstruction)
    return reconstruction


def get_reconstruction_report(db: Session, report_id: int):
    return (
        db.query(models.ReconstructionReport)
        .filter(models.ReconstructionReport.report_id == report_id)
        .first()
    )


def update_reconstruction_report(db: Session, report_id: int, **kwargs):
    reconstruction = db.query(models.ReconstructionReport).filter(
        models.ReconstructionReport.report_id == report_id
    ).first()
    if not reconstruction:
        raise ValueError("Reconstruction report not found")

    for key, value in kwargs.items():
        setattr(reconstruction, key, value)
    
    logger.info(f"Updating reconstruction report {report_id} with {kwargs}")
    logger.info(f"Current state before update: {reconstruction}")

    db.commit()
    db.refresh(reconstruction)
    return reconstruction


def get_mapping_report_map(db: Session, map_id: int, report_id:int):
    map = db.query(models.Map).filter(models.Map.id == map_id).first()
    if not map:
        raise ValueError(f"Map not found (map_id: {map_id})")
    
    mapping_report = db.query(models.MappingReport).filter(models.MappingReport.report_id == report_id).first()
    if not mapping_report:
        raise ValueError(f"Mapping Report for report_id ({report_id}) not found")
    
    if not map.mapping_report_id == mapping_report.id:
        raise ValueError(f"Trying to access a map from another report")
    
    return map