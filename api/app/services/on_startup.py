import redis
from app.config import config
from app.schemas.report import ReportOut
from app.database import get_db
from sqlalchemy.orm import Session
import app.crud.report as crud
import logging

def cleanup_lost_tasks():
    """Cleans up lost tasks by checking the Redis database for reports that are in progress but not completed."""

    r = redis.Redis(host=config.REDIS_HOST, port=config.REDIS_PORT, db=0)
    db = next(get_db())
    logger = logging.getLogger(__name__)
    
    #get reports and if the status is processing, preprocessing or queued, check redis for progress and if there is one end it and set to failed
    reports = crud.get_all(db)
    for report in reports:
        if report.status in ["processing", "preprocessing", "queued"]:
            crud.update_process(db, report.report_id, "failed", 0.0)
            logger.info(f"Report {report.report_id} was in status {report.status} but is now set to failed due to lost task cleanup.")

        # if report.type == "unset":
        #     report_short = crud.get_short_report(db, report.report_id)
        #     if report_short.mapping_report:
        #         #if it has a mapping report object, set the type to "mapping"
        #         crud.update_report_type(db, report.report_id, "mapping")

        try:
            task_id = r.get(f"report:{report.report_id}:task_id")
            if task_id:
                logger.info(f"Cleaning up lost task for report {report.report_id}")
                
                redis_status = r.get(f"report:{report.report_id}:status")
                if redis_status != None and redis_status != b"completed":
                    crud.update_process(db, report.report_id, "failed", 0.0)
                
                r.delete(f"report:{report.report_id}:task_id")
                r.delete(f"report:{report.report_id}:progress")
                r.delete(f"report:{report.report_id}:status")
                r.delete(f"report:{report.report_id}:message")
                logger.info(f"Cleaned up lost task for report {report.report_id}. Old status was {redis_status.decode('utf-8') if redis_status else 'None'} ")
        except Exception as e:
            logger.error(f"Error cleaning up lost task for report {report.report_id}: {e}")
    
        try:
            reconstruction_task_id = r.get(f"reconstruction:{report.report_id}:task_id")
            if reconstruction_task_id:
                logger.info(f"Cleaning up lost reconstruction task for report {report.report_id}")

                redis_status = r.get(f"reconstruction:{report.report_id}:status")
                if redis_status != None and redis_status != b"completed":
                    crud.update_process(db, report.report_id, "failed", 0.0)

                r.delete(f"reconstruction:{report.report_id}:task_id")
                r.delete(f"reconstruction:{report.report_id}:progress")
                r.delete(f"reconstruction:{report.report_id}:status")
                r.delete(f"reconstruction:{report.report_id}:message")
                logger.info(f"Cleaned up lost reconstruction task for report {report.report_id}. Old status was {redis_status.decode('utf-8') if redis_status else 'None'}")
        except Exception as e:
            logger.error(f"Error cleaning up lost reconstruction task for report {report.report_id}: {e}")

    # Detection status lives ONLY in Redis (no DB row), keyed by report id under
    # detection:{id}:{status,progress,message,task_id}. Both detection pipelines
    # (detection.run and detection_yolo.run) share this same key namespace, so a
    # single scan clears stuck tasks from either pipeline. This runs independently
    # of the DB report list and of task_id presence: any non-terminal detection
    # state at startup is by definition a lost task (workers don't survive a
    # restart), including a "queued" status orphaned before its task_id was set.
    _cleanup_lost_detection_tasks(r, logger)
    _cleanup_lost_colmap_tasks(r, logger)


def _cleanup_lost_detection_tasks(r, logger):
    """Clear Redis state for detection tasks left non-terminal across a restart.

    Scans for detection keys (covering both the `detection` and `detection_yolo`
    pipelines, which share the `detection:{id}:*` namespace), deletes the keys for
    any task not in a terminal state (`finished`/`error`), and purges both detection
    broker queues so no pre-restart message runs later.
    """
    # Collect candidate report ids from both status and task_id keys so we also
    # catch tasks orphaned before their task_id was written.
    report_ids = set()
    for pattern in ("detection:*:status", "detection:*:task_id"):
        for key in r.scan_iter(match=pattern):
            try:
                report_ids.add(key.split(b":")[1].decode("utf-8"))
            except (IndexError, UnicodeDecodeError):
                continue

    for report_id in report_ids:
        try:
            status = r.get(f"detection:{report_id}:status")
            if status in (b"finished", b"error"):
                continue  # terminal — leave a completed/failed run untouched

            r.delete(f"detection:{report_id}:task_id")
            r.delete(f"detection:{report_id}:progress")
            r.delete(f"detection:{report_id}:status")
            r.delete(f"detection:{report_id}:message")
            logger.info(
                f"Cleaned up lost detection task for report {report_id}. "
                f"Old status was {status.decode('utf-8') if status else 'None'}"
            )
        except Exception as e:
            logger.error(f"Error cleaning up lost detection task for report {report_id}: {e}")

    # Purge both detection broker queues (RobLab Rescue + YOLO). Other queues
    # (mapping, reconstruction_stella, description) are intentionally left alone.
    try:
        from app.services.celery_app import celery_app
        with celery_app.connection_for_write() as conn:
            for queue in ("detection", "detection_yolo"):
                purged = conn.default_channel.queue_purge(queue)
                if purged:
                    logger.info(f"Purged {purged} stuck message(s) from queue '{queue}'")
    except Exception as e:
        logger.error(f"Error purging detection broker queues: {e}")


def _cleanup_lost_colmap_tasks(r, logger):
    """Clear Redis state for COLMAP tasks left non-terminal across a restart.

    COLMAP status lives only in Redis under colmap:{id}:{status,progress,message,
    task_id} (no DB row — 3D availability is detected by the on-disk
    reconstruction.json). A worker does not survive a restart, so any
    non-terminal state at startup is a lost task. Mirrors the detection cleanup.
    """
    report_ids = set()
    for pattern in ("colmap:*:status", "colmap:*:task_id"):
        for key in r.scan_iter(match=pattern):
            try:
                report_ids.add(key.split(b":")[1].decode("utf-8"))
            except (IndexError, UnicodeDecodeError):
                continue

    for report_id in report_ids:
        try:
            status = r.get(f"colmap:{report_id}:status")
            if status in (b"completed", b"error"):
                continue  # terminal — leave it untouched

            r.delete(f"colmap:{report_id}:task_id")
            r.delete(f"colmap:{report_id}:progress")
            r.delete(f"colmap:{report_id}:status")
            r.delete(f"colmap:{report_id}:message")
            logger.info(
                f"Cleaned up lost COLMAP task for report {report_id}. "
                f"Old status was {status.decode('utf-8') if status else 'None'}"
            )
        except Exception as e:
            logger.error(f"Error cleaning up lost COLMAP task for report {report_id}: {e}")

    try:
        from app.services.celery_app import celery_app
        with celery_app.connection_for_write() as conn:
            purged = conn.default_channel.queue_purge("colmap")
            if purged:
                logger.info(f"Purged {purged} stuck message(s) from queue 'colmap'")
    except Exception as e:
        logger.error(f"Error purging colmap broker queue: {e}")