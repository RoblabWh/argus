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
from app.services.mapping.progress_updater import ProgressUpdater
from app.services.mapping.odm_mapping import summon_webODM_mapping_selections, process_webODM
import logging

r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0)
logger = logging.getLogger(__name__)

@celery_app.task
def process_report(report_id: int, settings: dict = None):
    db = next(get_db())
    progress_updater = ProgressUpdater(report_id, r, db)
    logger.info(f"Starting processing for report {report_id}")
    logger.info(f"Settings of type {type(settings)}: {settings}")
    try:
        progress_updater.update_progress("preprocessing", 1.0)
        report = crud.get_full_report(db, report_id, r)
        images = report.mapping_report.images
        mapping_report_id = report.mapping_report.id
        progress_updater.update_progress("preprocessing", 5.0)
        mapping_selections = preprocess_report(report_id, images, settings, db, progress_updater)
        
        
        if (settings['fast_mapping'] or settings["odm_processing"]) and len(mapping_selections) > 0:
            #delete old maps if they exist
            old_maps = map_crud.get_maps_by_mapping_report(db, mapping_report_id)
            for old_map in old_maps:
                logger.info(f"Deleting old map {old_map.id} for report {report_id}")
                if not old_map.odm and settings["fast_mapping"]:  # Only delete non-ODM maps
                    map_crud.delete(db, old_map.id)
                elif old_map.odm and settings["odm_processing"]:
                    map_crud.delete(db, old_map.id)

        odm_mapping_selections = []
        if settings["odm_processing"] and len(mapping_selections) > 0:
            odm_mapping_selections = summon_webODM_mapping_selections(mapping_selections)

        progress_updater.update_progress("preprocessing", 100.0)

        if settings['fast_mapping'] and len(mapping_selections) > 0:
            for map_index, mapping_selection in enumerate(mapping_selections):
                    progress_updater.set_map_index(map_index, len(mapping_selections)+len(odm_mapping_selections))
                    map_images(report_id, mapping_report_id, mapping_selection, settings, db, progress_updater, map_index=map_index)


        if settings['odm_processing'] and len(odm_mapping_selections) > 0:
            webODM_project_id = report.mapping_report.webodm_project_id if report.mapping_report else None
            for map_index, odm_mapping_selection in enumerate(odm_mapping_selections):
                # Process each ODM mapping task
                logger.info(f"Processing ODM mapping task {odm_mapping_selection['type']} for report {report_id}")
                progress_updater.set_map_index(map_index + len(mapping_selections), len(odm_mapping_selections) + len(mapping_selections))
                process_webODM(report_id, mapping_report_id, webODM_project_id, odm_mapping_selection, settings, db, progress_updater, map_index)

        progress_updater.update_progress("completed", 100.0)
    except Exception as e:
        logger.error(f"Error processing report {report_id}: {e}")
        # r.set(f"report:{report_id}:progress", -1.0)  # Indicate failure
        # crud.update_process(db, report_id, "failed", 0.0)
        progress_updater.update_progress("failed", 0.0)
        logger.error(f"Report {report_id} processing failed with error: {e}")
        raise e

    finally:
        db.close()

