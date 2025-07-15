import redis
from app.config import REDIS_HOST, REDIS_PORT
from app.schemas.report import ReportOut
from app.database import get_db
from sqlalchemy.orm import Session
import app.crud.report as crud

def cleanup_lost_tasks():
    """Cleans up lost tasks by checking the Redis database for reports that are in progress but not completed."""

    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0)
    db = next(get_db())
    
    #get reports and if the status is processing, preprocessing or queued, check redis for progress and if there is one end it and set to failed
    reports = crud.get_all(db)
    for report in reports:
        if report.status in ["processing", "preprocessing", "queued"]:
            task_id = r.get(f"report:{report.report_id}:task_id")
            if task_id:
                # Check if the task is still running
                print(f"Cleaning up lost task for report {report.report_id}", flush=True)
                # Set the report status to failed and progress to 0
                crud.update_process(db, report.report_id, "failed", 0.0)
                r.delete(f"report:{report.report_id}:task_id")
                r.delete(f"report:{report.report_id}:progress")