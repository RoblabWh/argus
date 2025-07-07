# entrypoint for celery task and in case of reprocessing defines the necessary processing steps
from app.services.mapping.celery_app import celery_app
import time
import redis
import os
from app.schemas.report import ProcessingSettings
from app.config import REDIS_PORT, REDIS_HOST
import app.crud.report as crud
from app.database import get_db
from sqlalchemy.orm import Session

r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0)

@celery_app.task
def process_report(report_id: int):
    db = next(get_db())
    try:
        #first get report from database
        report = crud.get_full_report(db, report_id)
        #print all report information
        print(f"Processing report {report_id}: {report}")
        print(f"Report of group: {report.group_id}")
        for i in range(10):
            time.sleep(1)
            progress = (i + 1) * 10.0
            r.set(f"report:{report_id}:progress", progress)
            print(f"Processing report {report_id}: {progress}%", flush=True)
            crud.update_process(db, report_id, "preprocessing", progress)

        for i in range(10):
            time.sleep(1)
            progress = 100.0 if i == 9 else (i + 1) * 10.0
            r.set(f"report:{report_id}:progress", progress)
            crud.update_process(db, report_id, "processing", progress)

        r.set(f"report:{report_id}:progress", 100.0)
        crud.update_process(db, report_id, "completed", 100.0)

    finally:
        db.close()