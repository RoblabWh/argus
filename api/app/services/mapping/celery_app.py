from celery import Celery

celery_app = Celery(
    "report_processing",
    broker="redis://redis:6379/0",
    backend="redis://redis:6379/0"
)

celery_app.autodiscover_tasks(["app.services.mapping"])


celery_app.conf.task_routes = {
    "tasks.*": {"queue": "default"}
}

