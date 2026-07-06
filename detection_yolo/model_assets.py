"""Model weight resolution shared by the Celery task and the startup warm-up.

Deliberately imports only huggingface_hub (no torch/transformers) so it stays
cheap to import from both predownload.py and tasks_detection_yolo.py.
"""
import logging
import os

from huggingface_hub import hf_hub_download

logger = logging.getLogger(__name__)

# Local dev/legacy weights baked into the image. Once the HF repo below is
# published, these files (and this override) can be removed from the repo.
LOCAL_YOLO_WEIGHTS = "./argus3_1280_yolo_11x_visdrone960_argus1280.pt"

YOLO_REPO_ID = os.getenv("ARGUS_YOLO_REPO_ID", "RoblabWhGe/ARGUS-YOLO11-x")
YOLO_FILENAME = os.getenv("ARGUS_YOLO_FILENAME", "best.pt")


def resolve_yolo_weights() -> str:
    """Return a filesystem path to the YOLO weights.

    Order: local file (dev override) -> HF cache (offline-safe, no etag
    round-trips) -> download from the public ARGUS repo into the persistent
    hf_cache volume.
    """
    if os.path.isfile(LOCAL_YOLO_WEIGHTS):
        return LOCAL_YOLO_WEIGHTS
    try:
        return hf_hub_download(YOLO_REPO_ID, filename=YOLO_FILENAME, local_files_only=True)
    except Exception:
        logger.info(
            "YOLO weights not in local cache — downloading %s/%s",
            YOLO_REPO_ID,
            YOLO_FILENAME,
        )
        return hf_hub_download(YOLO_REPO_ID, filename=YOLO_FILENAME)
