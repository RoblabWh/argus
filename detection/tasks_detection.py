from celery import Celery
import os
import json
import logging
import numpy as np
from transformer_pipeline.inference.datahandler import DataHandler
from transformer_pipeline.inference.inference_engine import Inferencer
from transformer_pipeline.inference.progress_tracker import ProgressTracker
from PIL import Image
import requests

import redis
REDIS_HOST = os.getenv("HOST_REDIS", "redis")
REDIS_PORT = int(os.getenv("PORT_REDIS", 6379))
r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0)
BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8008")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def preload_models():
    inferencer = Inferencer(score_thr=0.4)
    models = inferencer.which_models_are_available()
    logger.info(f"Available models: {models}")
    for model in models:
        inferencer.add_model(model)

    dummy_image = [np.zeros((640, 640, 3), dtype=np.uint8)]  # Dummy image for model loading
    save_path = "dummy_image.jpg"
    Image.fromarray(dummy_image[0]).save(save_path)
    logger.info(f"Dummy image saved to {save_path}")

    inferencer([save_path])  # Load models with dummy data
    
    inferencer = None  # Clear the inferencer to free memory

# Load model ONCE at startup (before tasks run)
# logger.info("Loading object detection model...")
# preload_models()
# logger.info("Model loaded.")

celery_app = Celery(
    "detector",
    broker=f"redis://{REDIS_HOST}:{REDIS_PORT}/0",
    backend=f"redis://{REDIS_HOST}:{REDIS_PORT}/0"
)


@celery_app.task(name="detection.run")
def run_detection(report_id: int, images: list[dict], max_splits: int = 0):
    logger.info(f"Starting detection for report {report_id} with {len(images)} images and max_splits={max_splits}")
    logger.info(f"Images: {type(images[:3])} - {images[:3]}")  # Log first 3 images for brevity
    try:
        r.set(f"detection:{report_id}:status", "running")
        r.set(f"detection:{report_id}:progress", 0)
    
        annotation_path = f"reports_data/{report_id}/annotations.json"
        progress_tracker = ProgressTracker(
            total_steps=4,
            broadcast_status_function=lambda status, progress, message: (
                r.set(f"detection:{report_id}:status", status),
                r.set(f"detection:{report_id}:progress", progress),
                r.set(f"detection:{report_id}:message", message)
            )
        )

        progress_tracker.start_step("starting", step_index=0)
        progress_tracker.set_message("Maybe already loading models...")

        datahandler = DataHandler(progress_tracker=progress_tracker)
        inferencer = Inferencer(score_thr=0.4, progress_tracker=progress_tracker, batch_size=2)
        models = inferencer.which_models_are_available()
        
        progress_tracker.set_message(f"Loading AI Models")
        for i, model in enumerate(models):
            inferencer.add_model(model)
            progress_tracker.update_step_progress_of_total(i + 1, len(models))

        datahandler.set_image_paths([file["url"] for file in images])
        datahandler.args.split = True
        datahandler.args.max_splitting_steps = max_splits


        progress_tracker.start_step("Preprocessing", step_index=1)
        progress_tracker.set_message("Preprocessing images")

        datahandler.preprocess()
        data = datahandler.get_data()

        progress_tracker.start_step("Ai processing", step_index=2)
        progress_tracker.set_message("Running inference on images")

        results = inferencer(data)

        progress_tracker.start_step("Postprocessing", step_index=3)
        progress_tracker.set_message("Processing and merging results")

        result = datahandler.postprocess(results)
        datahandler.set_ann_path(annotation_path)
        datahandler.save_annotation(result)

        progress_tracker.set_message("Saving results to database and displaying detections")

        #datahandler.show(result)
        results_data = reformat_ann(annotation_path, images)
        

        # send results to backend API
        url = f"{BACKEND_URL}/detections/r/{report_id}"
        resp = requests.put(url, json={"detections": results_data}, timeout=30)
        resp.raise_for_status()

        r.set(f"detection:{report_id}:status", "finished")
        r.set(f"detection:{report_id}:progress", 100)
        r.set(f"detection:{report_id}:message", "Detection completed successfully")
    except Exception as e:
        logger.error(f"Error during detection for report {report_id}: {e}")
        r.set(f"detection:{report_id}:status", "failed")
        r.set(f"detection:{report_id}:message", str(e))
        r.set(f"detection:{report_id}:progress", 0)


def reformat_ann(ann_path: str, images: list[dict]):
    file_lookup = {os.path.basename(f["url"]): f["id"] for f in images}

    data = None
    with open(ann_path, 'r') as json_file:
        data = json.load(json_file)

    print('found', len(data["annotations"]), 'objects')

    categories = {cat["id"]: cat["name"] for cat in data.get("categories", [])}

    # Map result image ids to original ids
    img_id_map = {}
    for img in data.get("images", []):
        fname = os.path.basename(img["file_name"])
        if fname in file_lookup:
            img_id_map[img["id"]] = file_lookup[fname]

    # Replace annotation image_ids with original ids
    for ann in data.get("annotations", []):
        if ann["image_id"] in img_id_map:
            ann["image_id"] = img_id_map[ann["image_id"]]
        ann["category_name"] = categories.get(ann["category_id"], "unknown")

    return data.get("annotations", [])




    # for image in data["images"]:
    #     image["file_name"] = image["file_name"].split("/")[-1]

    # for category in data["categories"]:
    #     category["colorHSL"] = [(300 - int((category["id"] + 1) / len(data["categories"]) * 360)) % 360, 100, 50]

    # #add a version tag to the json file
    # data["version"] = 1.0

    # with open(ann_path, 'w') as json_file:
    #     json.dump(data, json_file)

    # return data

