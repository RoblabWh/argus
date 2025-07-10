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
from app.services.mapping.preprocessing import preprocess_report

r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0)

@celery_app.task
def process_report(report_id: int):
    db = next(get_db())
    try:
        report = crud.get_full_report(db, report_id, r)
        images = report.mapping_report.images
        mapping_selections = preprocess_report(images, report_id, db, update_progress_func=update_progress)

        for i in range(10):
            time.sleep(1)
            progress = 100.0 if i == 9 else (i + 1) * 10.0
            r.set(f"report:{report_id}:progress", progress)
            crud.update_process(db, report_id, "processing", progress)

        r.set(f"report:{report_id}:progress", 100.0)
        crud.update_process(db, report_id, "completed", 100.0)
    except Exception as e:
        print(f"Error processing report {report_id}: {e}")
        r.set(f"report:{report_id}:progress", -1.0)  # Indicate failure
        crud.update_process(db, report_id, "failed", 0.0)
        raise e

    finally:
        db.close()

def update_progress(report_id: int, stage: str, progress: float, db: Session):
    r.set(f"report:{report_id}:progress", progress)
    crud.update_process(db, report_id, stage, progress)
