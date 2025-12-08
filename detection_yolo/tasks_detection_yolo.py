from celery import Celery
import os
import logging
import redis
import requests

from ultralytics import YOLO
from yolo_inference import YOLOInferencer   # NEW MODULE (see next step)

from huggingface_hub import hf_hub_download


logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

REDIS_HOST = os.getenv("HOST_REDIS", "redis")
REDIS_PORT = int(os.getenv("PORT_REDIS", 6379))
BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8008")
r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0)

# Celery app for *this* pipeline
celery_app = Celery(
    "detector_yolo",
    broker=f"redis://{REDIS_HOST}:{REDIS_PORT}/0",
    backend=f"redis://{REDIS_HOST}:{REDIS_PORT}/0"
)



@celery_app.task(name="detection_yolo.run")
def run_detection_yolo(report_id: int, images: list[dict]):
    logger.info(f"[YOLO] Starting detection for report {report_id}")

    r.set(f"detection:{report_id}:status", "running")
    r.set(f"detection:{report_id}:progress", 0)
    r.set(f"detection:{report_id}:message", "Initializing YOLOv11 inference…")

    def set_progress(step: int, total_steps: int, message: str):
        progress = int((step / total_steps) * 100)
        r.set(f"detection:{report_id}:progress", progress)
        r.set(f"detection:{report_id}:message", message)

    try:
        model_path = hf_hub_download(
            repo_id="StephanST/WALDO30",
            filename="WALDO30_yolov8m_640x640.pt"
        )
        # model_path = hf_hub_download(
        #     repo_id="erbayat/yolov11n-visdrone",
        #     filename="best.pt"
        # )
        # model_path = "yolo11l.pt"
        infer = YOLOInferencer(model_name=model_path, progress_callback=set_progress)

        r.set(f"detection:{report_id}:message", "Running YOLOv11 inference…")

        # create 4 image long batches for progress tracking
        batch_size = 4
        total_batches = (len(images) + batch_size - 1) // batch_size
        for i in range(total_batches):
            batch_images = images[i*batch_size:(i+1)*batch_size]
            annotations = infer.run(batch_images)
            url = f"{BACKEND_URL}/detections/r/{report_id}"
            resp = requests.put(url, json={"detections": annotations}, timeout=30)
            resp.raise_for_status()
            set_progress(i + 1, total_batches, f"Processed batch {i + 1} of {total_batches}")
        # annotations = infer.run(images)
        # logger.info(f"[YOLO] Inference completed for report {report_id}")
        # logger.info(f"[YOLO] Annotations: {annotations[:2]}")  # Log first 2 annotations for brevity

        # Save result as your backend expects:
        # url = f"{BACKEND_URL}/detections/r/{report_id}"
        # resp = requests.put(url, json={"detections": annotations}, timeout=30)
        # resp.raise_for_status()

        r.set(f"detection:{report_id}:status", "finished")
        r.set(f"detection:{report_id}:progress", 100)
        r.set(f"detection:{report_id}:message", "Detection with YOLO completed successfully")

    except Exception as e:
        logger.error(e)
        r.set(f"detection:{report_id}:status", "error")
        r.set(f"detection:{report_id}:message", str(e))
        r.set(f"detection:{report_id}:progress", 0)
        raise
