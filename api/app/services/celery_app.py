from celery import Celery
import logging
from app.config import REDIS_HOST, REDIS_PORT

logging.basicConfig(
    level=logging.INFO,  # Or DEBUG
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

celery_app = Celery(
    "report_processing",
    broker=f"redis://{REDIS_HOST}:{REDIS_PORT}/0",
    backend=f"redis://{REDIS_HOST}:{REDIS_PORT}/0"
)

celery_app.autodiscover_tasks(["app.services.mapping"])
celery_app.autodiscover_tasks(["app.services.image_describer"])



celery_app.conf.task_routes = {
    "mapping.*": {"queue": "mapping"},
    "detection.*": {"queue": "detection"},
    "description.*": {"queue": "description"},
}

