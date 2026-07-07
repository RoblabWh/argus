"""Background status watchdog.

Owns the write-side reconciliation that used to hide inside polling GET
handlers (crud.get_process_status, GET /reports/{id}/auto_description):
detecting crashed/lost tasks and fixing DB/Redis state. Running it here means
failure detection no longer depends on a browser polling the endpoints, and
the polling GETs become pure reads.

Started as an asyncio task from the FastAPI lifespan handler; each tick runs
the sync DB/Redis/Celery work in the threadpool.
"""

import asyncio
import logging

from fastapi.concurrency import run_in_threadpool

logger = logging.getLogger(__name__)

WATCHDOG_INTERVAL_SECONDS = 10

ACTIVE_REPORT_STATES = ("queued", "preprocessing", "processing")


def _reconcile_reports() -> None:
    import app.crud.report as report_crud
    from app import models
    from app.database import get_db
    from app.services import events as events_service

    r = events_service.get_sync_redis()
    db = next(get_db())
    try:
        active_ids = [
            row[0]
            for row in db.query(models.Report.report_id)
            .filter(models.Report.status.in_(ACTIVE_REPORT_STATES))
            .all()
        ]
        for report_id in active_ids:
            try:
                if report_crud.reconcile_report_status(db, report_id, r):
                    report = (
                        db.query(models.Report)
                        .filter(models.Report.report_id == report_id)
                        .first()
                    )
                    logger.info(
                        f"Watchdog reconciled report {report_id} -> {report.status}"
                    )
                    events_service.publish_event(
                        r,
                        report_id,
                        events_service.EVENT_REPORT_STATUS,
                        status=report.status,
                        progress=report.progress,
                    )
            except Exception:
                logger.exception(f"Watchdog failed to reconcile report {report_id}")
    finally:
        db.close()


def _reconcile_descriptions() -> None:
    """Mark auto-description runs whose Celery task died as errored.

    Moved from GET /reports/{id}/auto_description. The Celery inspect ping in
    task_is_really_active is comparatively slow, so it only runs when an
    active description key actually exists (usually none).
    """
    from app.services import events as events_service
    from app.services.celery_app import task_is_really_active

    r = events_service.get_sync_redis()
    for key in r.scan_iter(match="description:*:status"):
        status = r.get(key)
        if not status or status.decode() not in ("processing", "queued"):
            continue
        try:
            report_id = int(key.decode().split(":")[1])
        except (IndexError, ValueError):
            continue
        task_id = r.get(f"description:{report_id}:task_id")
        if task_id and not task_is_really_active(task_id.decode()):
            r.set(f"description:{report_id}:status", "error")
            r.set(f"description:{report_id}:progress", 100.0)
            logger.info(f"Watchdog marked dead description task for report {report_id} as error")
            events_service.publish_event(
                r,
                report_id,
                events_service.EVENT_DESCRIPTION_STATUS,
                status="error",
                progress=100.0,
            )


def _tick() -> None:
    _reconcile_reports()
    _reconcile_descriptions()


async def watchdog_loop() -> None:
    while True:
        try:
            await run_in_threadpool(_tick)
        except Exception:
            logger.exception("Status watchdog tick failed")
        await asyncio.sleep(WATCHDOG_INTERVAL_SECONDS)
