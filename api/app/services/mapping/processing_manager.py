# entrypoint for celery task and in case of reprocessing defines the necessary processing steps
from app.services.mapping.celery_app import celery_app
import time
import redis
import os
from app.schemas.report import ProcessingSettings
from app.config import REDIS_PORT, REDIS_HOST
import app.crud.report as crud
import app.crud.map as map_crud
from app.database import get_db
from sqlalchemy.orm import Session
from app.services.mapping.preprocessing import preprocess_report
from app.services.mapping.fast_mapping import map_images
import logging

r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0)
logger = logging.getLogger(__name__)


@celery_app.task
def process_report(report_id: int, settings: dict = None):
    db = next(get_db())
    logger.info(f"Starting processing for report {report_id}")
    logger.info(f"Settings of type {type(settings)}: {settings}")
    try:
        report = crud.get_full_report(db, report_id, r)
        images = report.mapping_report.images
        mapping_report_id = report.mapping_report.id
        mapping_selections = preprocess_report(report_id, images, settings, db, update_progress_func=update_progress)
        
        
        if settings['fast_mapping'] and len(mapping_selections) > 0:
            #delete old maps if they exist
            old_maps = map_crud.get_maps_by_mapping_report(db, mapping_report_id)
            for old_map in old_maps:
                logger.info(f"Deleting old map {old_map.id} for report {report_id}")
                if not old_map.odm: # Only delete non-ODM maps
                    map_crud.delete(db, old_map.id)

        update_progress(report_id, "preprocessing", 100.0, db)

        if settings['fast_mapping'] and len(mapping_selections) > 0:
            for map_index, mapping_selection in enumerate(mapping_selections):
                    map_images(report_id, mapping_report_id, mapping_selection, settings, db, update_progress_func=update_progress, total_maps=len(mapping_selections), map_index=map_index)
        else:
            logger.info(f"Skipping fast mapping for report {report_id} as fast_mapping is set to False")


        # r.set(f"report:{report_id}:progress", 100.0)
        # crud.update_process(db, report_id, "completed", 100.0)
        update_progress(report_id, "completed", 100.0, db)
    except Exception as e:
        logger.error(f"Error processing report {report_id}: {e}")
        # r.set(f"report:{report_id}:progress", -1.0)  # Indicate failure
        # crud.update_process(db, report_id, "failed", 0.0)
        update_progress(report_id, "failed", 0.0, db)
        logger.error(f"Report {report_id} processing failed with error: {e}")
        raise e

    finally:
        db.close()

def update_progress(report_id: int, stage: str, progress: float, db: Session):
    crud.update_process(db, report_id, stage, progress)
    r.set(f"report:{report_id}:progress", progress)
