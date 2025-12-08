from celery import Celery
import logging
from app.config import config

logging.basicConfig(
    level=logging.INFO,  # Or DEBUG
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

celery_app = Celery(
    "report_processing",
    broker=f"redis://{config.REDIS_HOST}:{config.REDIS_PORT}/0",
    backend=f"redis://{config.REDIS_HOST}:{config.REDIS_PORT}/0"
)

celery_app.autodiscover_tasks(["app.services.mapping"])
celery_app.autodiscover_tasks(["app.services.image_describer"])



celery_app.conf.task_routes = {
    "mapping.*": {"queue": "mapping"},
    "detection.*": {"queue": "detection"},
    "description.*": {"queue": "description"},
    "detection_yolo.*": {"queue": "detection_yolo"},
}

def task_is_really_active(task_id: str) -> bool:
    i = celery_app.control.inspect()
    for worker_tasks in (i.active() or {}).values():
        if any(t["id"] == task_id for t in worker_tasks):
            return True
    for worker_tasks in (i.scheduled() or {}).values():
        if any(t["id"] == task_id for t in worker_tasks):
            return True
    for worker_tasks in (i.reserved() or {}).values():
        if any(t["id"] == task_id for t in worker_tasks):
            return True
    return False