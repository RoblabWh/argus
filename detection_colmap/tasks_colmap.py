"""COLMAP SfM Celery worker (queue: ``colmap``).

Runs Stage 1 (Structure-from-Motion + geo-registration) for a report when the
user opted into 3D reconstruction. Writes its artifacts to the shared volume at
``reports_data/{report_id}/colmap/`` where the YOLO worker later reads them for
3D re-identification.

Status is tracked purely in Redis under ``colmap:{report_id}:{status,progress,
message}`` (mirrors the detection / stella pipelines). No DB row is created;
3D availability is detected downstream by the presence of ``reconstruction.json``.
"""
from celery import Celery
import os
import logging

import redis
import requests

from colmap_runner import build_reconstruction, ColmapError

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

REDIS_HOST = os.getenv("HOST_REDIS", "redis")
REDIS_PORT = int(os.getenv("PORT_REDIS", 6379))
BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8008")
r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0)

celery_app = Celery(
    "colmap",
    broker=f"redis://{REDIS_HOST}:{REDIS_PORT}/0",
    backend=f"redis://{REDIS_HOST}:{REDIS_PORT}/0",
)


@celery_app.task(name="colmap.run")
def run_colmap(report_id: int, image_paths: dict, results_path: str,
               options: dict = None):
    """Build a 3D reconstruction for ``report_id``.

    Args:
        report_id: report id (for redis status keys + callback).
        image_paths: ``{basename: absolute_path}`` of the reconstruction set,
            as seen from inside this container (shared-volume mount).
        results_path: output dir inside this container
            (``.../reports_data/{report_id}/colmap``).
        options: ``{"dense": bool}``.
    """
    options = options or {}
    logger.info("[colmap] Starting reconstruction for report %s", report_id)
    r.set(f"colmap:{report_id}:status", "running")
    r.set(f"colmap:{report_id}:progress", 0)
    r.set(f"colmap:{report_id}:message", "Initializing COLMAP…")

    def progress_cb(message: str, percent: int):
        r.set(f"colmap:{report_id}:progress", int(percent))
        r.set(f"colmap:{report_id}:message", message)

    try:
        summary = build_reconstruction(
            image_paths, results_path, options=options, progress_cb=progress_cb
        )

        r.set(f"colmap:{report_id}:status", "completed")
        r.set(f"colmap:{report_id}:progress", 100)
        r.set(
            f"colmap:{report_id}:message",
            f"Reconstruction complete — "
            f"{summary['registered_images']}/{summary['total_images']} images registered",
        )

        # Best-effort completion callback (lets the API note 3D availability /
        # surface the registration rate). Not required — the YOLO worker only
        # needs the on-disk reconstruction.json.
        try:
            requests.post(
                f"{BACKEND_URL}/reports/{report_id}/colmap/complete",
                json={
                    "registered_images": summary["registered_images"],
                    "total_images": summary["total_images"],
                    "reconstruction_mode": summary["reconstruction_mode"],
                    "geo_reg_residual_m": summary["geo_reg_residual_m"],
                },
                timeout=30,
            )
        except Exception as cb_err:  # noqa: BLE001 - callback is best-effort
            logger.warning("[colmap] completion callback failed: %s", cb_err)

        return {"report_id": report_id, "registered": summary["registered_images"]}

    except ColmapError as e:
        logger.error("[colmap] reconstruction failed for report %s: %s", report_id, e)
        r.set(f"colmap:{report_id}:status", "error")
        r.set(f"colmap:{report_id}:message", str(e))
        r.set(f"colmap:{report_id}:progress", 0)
        raise
    except Exception as e:  # noqa: BLE001
        logger.error("[colmap] unexpected error for report %s: %s", report_id, e)
        r.set(f"colmap:{report_id}:status", "error")
        r.set(f"colmap:{report_id}:message", str(e))
        r.set(f"colmap:{report_id}:progress", 0)
        raise
