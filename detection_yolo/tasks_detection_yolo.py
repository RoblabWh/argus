from celery import Celery
import json
import os
import logging
import redis
import requests
import gc
import time
import torch

from ultralytics import YOLO
from yolo_inference import YOLOInferencer

from model_assets import get_pipeline_specs, resolve_yolo_weights
from reid.by_dinov3 import run_reid
from reid.by_3d_dinov3 import run_reid_3d
from reid import localize
from reid.embeddings import unload_models as unload_reid_models


logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.WARNING)

# docker-compose passes REDIS_HOST/REDIS_PORT; the *_REDIS names are kept as
# fallback for older deployments.
REDIS_HOST = os.getenv("REDIS_HOST") or os.getenv("HOST_REDIS", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT") or os.getenv("PORT_REDIS", 6379))
BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8008")
DEVICE = os.getenv("DEVICE", "cuda:0")
r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0)

# Celery app for *this* pipeline
celery_app = Celery(
    "detector_yolo",
    broker=f"redis://{REDIS_HOST}:{REDIS_PORT}/0",
    backend=f"redis://{REDIS_HOST}:{REDIS_PORT}/0"
)


def publish_status(report_id: int, *, status=None, progress=None, message=None, data=None):
    """Push a detection_status event to live SSE subscribers.

    Additive to the detection:{id}:* keys (which stay the source of truth for
    snapshots/polling). Channel + envelope are the cross-container contract —
    see api/SSE_MIGRATION_PLAN.md. Fire-and-forget: must never break the task.
    """
    payload = {
        "report_id": report_id,
        "type": "detection_status",
        "status": status,
        "progress": progress,
        "message": message,
        "data": data or {},
        "ts": time.time(),
    }
    try:
        r.publish(f"argus:events:report:{report_id}", json.dumps(payload))
    except Exception:
        logger.warning("Failed to publish detection_status event for report %s", report_id, exc_info=True)



def run_reid_clustering(report_id: int, exclude_classes: set[str] | None = None):
    """Cluster a report's detections into unique objects, in-place via the API.

    Fetches the saved detections back (to learn their DB ids) plus per-image
    georeferencing, runs the DINOv3 reID, and pushes the resulting clusters.
    ``exclude_classes`` drops detections by class name — used for classes
    emitted by non-reID models (e.g. fire/smoke) that were saved in the same
    run; they keep a null unique_object_id. The detection status stays
    "running" with progress messages throughout; callers flip it to "finished"
    afterwards. All errors are swallowed so a reID failure never discards the
    already-saved detections.
    """
    try:
        r.set(f"detection:{report_id}:progress", 90)
        r.set(
            f"detection:{report_id}:message",
            "Detections complete — re-identifying objects…",
        )
        publish_status(report_id, status="running", progress=90,
                       message="Detections complete — re-identifying objects…")

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
        #
        # This gate is deliberate and applies to the 3D path too, even though it
        # could localize such detections from the reconstruction alone:
        #   - an image without a map element is usually NOT nadir, so its crops
        #     look very different from the rest of the flight and DINOv3 cosine
        #     against the nadir sightings of the same object is unreliable — the
        #     very signal the sanity gates and the cleanup pass run on;
        #   - without a map element the detection cannot be drawn on the map, so
        #     a cluster containing one would be partly invisible in the report.
        mapped_image_ids = {iid for iid, img in images.items() if img.get("corners_gps")}
        exclude_classes = exclude_classes or set()
        reid_detections = [
            d for d in detections
            if d["image_id"] in mapped_image_ids and d.get("class_name") not in exclude_classes
        ]

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
                "[YOLO] Skipping reID for report %s (%d eligible detections of %d total, "
                "%d classes excluded, 3d=%s)",
                report_id,
                len(reid_detections),
                len(detections),
                len(exclude_classes),
                has_3d,
            )
            return

        def progress_cb(message: str, fraction: float):
            # Map reID progress into the 90..99 band so the bar keeps moving
            # without prematurely hitting 100 (reserved for "finished").
            progress = 90 + int(fraction * 9)
            r.set(f"detection:{report_id}:progress", progress)
            r.set(f"detection:{report_id}:message", message)
            publish_status(report_id, status="running", progress=progress, message=message)

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
def run_detection_yolo(report_id: int, images: list[dict], hf_token: str | None = None,
                       pipeline: str = "objects"):
    logger.info(f"[YOLO] Starting detection for report {report_id} (pipeline: {pipeline})")

    # The API forwards the deployment's HF token with every task, so a token
    # saved on the settings page works on the next run without a container
    # restart. huggingface_hub picks it up from the environment when the
    # gated DINOv3 weights need downloading.
    if hf_token:
        os.environ["HF_TOKEN"] = hf_token

    r.set(f"detection:{report_id}:status", "running")
    r.set(f"detection:{report_id}:progress", 0)
    r.set(f"detection:{report_id}:message", "Initializing YOLO inference…")
    publish_status(report_id, status="running", progress=0, message="Initializing YOLO inference…")

    def set_progress(step: int, total_steps: int, message: str):
        # Inference owns the 0-90 band; reID continues 90-99 and "finished" is
        # 100, so the bar never moves backwards.
        progress = int((step / total_steps) * 90)
        r.set(f"detection:{report_id}:progress", progress)
        r.set(f"detection:{report_id}:message", message)
        publish_status(report_id, status="running", progress=progress, message=message)

    try:
        specs = get_pipeline_specs(pipeline)

        # Detections from all active models accumulate on the report (the API
        # clears old ones at dispatch). Classes emitted by non-reID models are
        # collected here so reID leaves them alone (null unique_object_id).
        # Note: if a non-reID model ever shared a class name with an reID
        # model, those shared-name detections would be excluded too — the
        # current models have disjoint class sets.
        reid_excluded_classes: set[str] = set()

        batch_size = 16
        total_batches = (len(images) + batch_size - 1) // batch_size
        overall_batches = len(specs) * total_batches

        for model_idx, (model_name, spec) in enumerate(specs):
            logger.info("[YOLO] Running model %s (%s/%s)", model_name, spec.repo_id, spec.filename)
            model_path = resolve_yolo_weights(spec)
            infer = YOLOInferencer(model_name=model_path, imgsz=spec.imgsz, progress_callback=set_progress, device=DEVICE)
            r.set(f"detection:{report_id}:message", f"Running YOLO inference ({model_name})…")

            for i in range(total_batches):
                batch_images = images[i*batch_size:(i+1)*batch_size]
                annotations = infer.run(batch_images)
                if spec.class_map:
                    for det in annotations:
                        det["category_name"] = spec.class_map.get(det["category_name"], det["category_name"])
                if spec.keep_classes is not None:
                    annotations = [det for det in annotations if det["category_name"] in spec.keep_classes]
                if not spec.run_reid:
                    reid_excluded_classes.update(det["category_name"] for det in annotations)
                url = f"{BACKEND_URL}/detections/r/{report_id}"
                resp = requests.put(url, json={"detections": annotations}, timeout=30)
                resp.raise_for_status()
                set_progress(
                    model_idx * total_batches + i + 1,
                    overall_batches,
                    f"[{model_name}] Processed batch {i + 1} of {total_batches}",
                )

            # Free this model before loading the next one, so two models never
            # hold VRAM at the same time (and reID starts with a clean GPU).
            del infer
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                torch.cuda.ipc_collect()

        # ------------------------------------------------------------------
        # Re-identification: join detections of the same physical object into
        # tracks/clusters (DINOv3 appearance + GPS proximity). Best-effort: the
        # detections are already saved/shown, so a reID failure must never
        # discard them — log it and still mark the task finished. Classes from
        # the experimental fire models are excluded (no persistent identity).
        # ------------------------------------------------------------------
        if any(spec.run_reid for _, spec in specs):
            run_reid_clustering(report_id, exclude_classes=reid_excluded_classes)
            final_message = "Detection + reID completed successfully"
        else:
            logger.info("[YOLO] Skipping reID — no active model uses it")
            final_message = "Detection completed successfully"

        r.set(f"detection:{report_id}:status", "finished")
        r.set(f"detection:{report_id}:progress", 100)
        r.set(f"detection:{report_id}:message", final_message)
        publish_status(report_id, status="finished", progress=100,
                       message=final_message)

    except Exception as e:
        logger.error(e)
        r.set(f"detection:{report_id}:status", "error")
        r.set(f"detection:{report_id}:message", str(e))
        r.set(f"detection:{report_id}:progress", 0)
        publish_status(report_id, status="error", progress=0, message=str(e))
        raise
