from celery import Celery
import os
import logging
import redis
import requests
import gc
import torch

from ultralytics import YOLO
from yolo_inference import YOLOInferencer   # NEW MODULE (see next step)

from huggingface_hub import hf_hub_download

from reid.by_dinov3 import run_reid
from reid.by_3d_dinov3 import run_reid_3d
from reid import localize
from reid.embeddings import unload_models as unload_reid_models


logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.WARNING)

REDIS_HOST = os.getenv("HOST_REDIS", "redis")
REDIS_PORT = int(os.getenv("PORT_REDIS", 6379))
BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8008")
DEVICE = os.getenv("DEVICE", "cuda:0")
r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0)

# Celery app for *this* pipeline
celery_app = Celery(
    "detector_yolo",
    broker=f"redis://{REDIS_HOST}:{REDIS_PORT}/0",
    backend=f"redis://{REDIS_HOST}:{REDIS_PORT}/0"
)



def run_reid_clustering(report_id: int):
    """Cluster a report's detections into unique objects, in-place via the API.

    Fetches the saved detections back (to learn their DB ids) plus per-image
    georeferencing, runs the DINOv3 reID, and pushes the resulting clusters.
    The detection status stays "running" with progress messages throughout;
    callers flip it to "finished" afterwards. All errors are swallowed so a
    reID failure never discards the already-saved detections.
    """
    try:
        r.set(f"detection:{report_id}:progress", 90)
        r.set(
            f"detection:{report_id}:message",
            "Detections complete — re-identifying objects…",
        )

        resp = requests.get(f"{BACKEND_URL}/detections/r/{report_id}/reid_input", timeout=60)
        resp.raise_for_status()
        payload = resp.json()
        detections = payload.get("detections", [])
        images = {img["id"]: img for img in payload.get("images", [])}

        # Re-ID only considers detections from images actually placed in the map
        # (those have GPS corners). Detections from non-mapped images are excluded
        # from re-ID entirely and keep a null unique_object_id — they are neither
        # clustered nor emitted as singletons. (assign_unique_object_clusters
        # resets the whole report to null before writing, so any detection we omit
        # here stays null for free.)
        mapped_image_ids = {iid for iid, img in images.items() if img.get("corners_gps")}
        reid_detections = [d for d in detections if d["image_id"] in mapped_image_ids]

        # A COLMAP 3D reconstruction (built during processing when the user opted
        # in) lives in the shared volume. Its presence selects the stronger 3D
        # weighted-multipass reID; otherwise we gracefully fall back to the 2D
        # DINOv3 + bilinear-GPS approach.
        colmap_dir = os.path.join("reports_data", str(report_id), "colmap")
        has_3d = os.path.isfile(os.path.join(colmap_dir, "reconstruction.json"))

        # Every reid_detection is from a mapped (georeferenced) image by
        # construction, so we only need enough of them to form a pair.
        if len(reid_detections) < 2:
            logger.info(
                "[YOLO] Skipping reID for report %s (%d mapped-image detections of %d total, 3d=%s)",
                report_id,
                len(reid_detections),
                len(detections),
                has_3d,
            )
            return

        def progress_cb(message: str, fraction: float):
            # Map reID progress into the 90..99 band so the bar keeps moving
            # without prematurely hitting 100 (reserved for "finished").
            r.set(f"detection:{report_id}:progress", 90 + int(fraction * 9))
            r.set(f"detection:{report_id}:message", message)

        # Optionally dump the crops fed to DINOv3 for manual inspection. Lands
        # under the shared volume at reports_data/{report_id}/reid_crops/.
        dump_dir = None
        if os.getenv("REID_DUMP_CROPS", "false").lower() not in ("0", "false", "no", ""):
            dump_dir = os.path.join("reports_data", str(report_id), "reid_crops")

        clusters = None
        if has_3d:
            try:
                r.set(f"detection:{report_id}:message", "Localizing detections in 3D…")
                positions = localize.compute_annotation_positions(reid_detections, images, colmap_dir)
                if positions:
                    logger.info(
                        "[YOLO] Using 3D reID for report %s (%d/%d mapped-image detections localized)",
                        report_id, len(positions), len(reid_detections),
                    )
                    clusters = run_reid_3d(
                        reid_detections, images, positions,
                        progress_cb=progress_cb, dump_dir=dump_dir,
                    )
                else:
                    logger.warning(
                        "[YOLO] 3D reconstruction present but no detection localized for "
                        "report %s — falling back to 2D reID", report_id,
                    )
            except Exception as e3d:  # noqa: BLE001 - never lose detections to a 3D failure
                logger.error("[YOLO] 3D reID failed for report %s: %s — falling back to 2D", report_id, e3d)

        if clusters is None:
            clusters = run_reid(reid_detections, images, progress_cb=progress_cb, dump_dir=dump_dir)

        put = requests.put(
            f"{BACKEND_URL}/detections/r/{report_id}/unique_objects",
            json={"clusters": {str(uid): det_ids for uid, det_ids in clusters.items()}},
            timeout=60,
        )
        put.raise_for_status()
        logger.info("[YOLO] reID assigned %d objects for report %s", len(clusters), report_id)
    except Exception as e:  # noqa: BLE001 - reID is an enhancement, not required
        logger.error("[YOLO] reID failed for report %s: %s", report_id, e)
    finally:
        unload_reid_models()


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
        # local_model_path = "./argus3_1280_yolo_11l_visdrone960_argus1280.pt"
        local_model_path = "./argus3_1280_yolo_11x_visdrone960_argus1280.pt" # Still local need publishing to HF hub
        model_path = (
            local_model_path
            if os.path.isfile(local_model_path)
            else hf_hub_download(
                repo_id="erbayat/yolov11n-visdrone",
                filename="best.pt",
            )
        )
        imgsz = 1280
        infer = YOLOInferencer(model_name=model_path, imgsz=imgsz, progress_callback=set_progress, device=DEVICE)
        r.set(f"detection:{report_id}:message", "Running YOLOv11 inference…")

        # create 4 image long batches for progress tracking
        batch_size = 16
        total_batches = (len(images) + batch_size - 1) // batch_size
        for i in range(total_batches):
            batch_images = images[i*batch_size:(i+1)*batch_size]
            annotations = infer.run(batch_images)
            url = f"{BACKEND_URL}/detections/r/{report_id}"
            resp = requests.put(url, json={"detections": annotations}, timeout=30)
            resp.raise_for_status()
            set_progress(i + 1, total_batches, f"Processed batch {i + 1} of {total_batches}")
        del infer
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.ipc_collect()

        # ------------------------------------------------------------------
        # Re-identification: join detections of the same physical object into
        # tracks/clusters (DINOv3 appearance + GPS proximity). Best-effort: the
        # detections are already saved/shown, so a reID failure must never
        # discard them — log it and still mark the task finished.
        # ------------------------------------------------------------------
        run_reid_clustering(report_id)

        r.set(f"detection:{report_id}:status", "finished")
        r.set(f"detection:{report_id}:progress", 100)
        r.set(f"detection:{report_id}:message", "Detection + reID completed successfully")

    except Exception as e:
        logger.error(e)
        r.set(f"detection:{report_id}:status", "error")
        r.set(f"detection:{report_id}:message", str(e))
        r.set(f"detection:{report_id}:progress", 0)
        raise
