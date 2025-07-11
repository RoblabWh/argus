from celery import Celery
import logging

logging.basicConfig(
    level=logging.INFO,  # Or DEBUG
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

celery_app = Celery(
    "report_processing",
    broker="redis://redis:6379/0",
    backend="redis://redis:6379/0"
)

celery_app.autodiscover_tasks(["app.services.mapping"])


celery_app.conf.task_routes = {
    "tasks.*": {"queue": "default"}
}

