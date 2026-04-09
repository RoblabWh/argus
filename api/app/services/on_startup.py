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

        try:
            detection_task_id = r.get(f"detection:{report.report_id}:task_id")
            if detection_task_id:
                logger.info(f"Cleaning up lost detection task for report {report.report_id}")

                # detection status is only lives in redis, no extra cleanup in database needed

                r.delete(f"detection:{report.report_id}:task_id")
                r.delete(f"detection:{report.report_id}:progress")
                r.delete(f"detection:{report.report_id}:status")
                r.delete(f"detection:{report.report_id}:message")
                logger.info(f"Cleaned up lost detection task for report {report.report_id}")
        except Exception as e:
            logger.error(f"Error cleaning up lost detection task for report {report.report_id}: {e}")