"""Model weight resolution shared by the Celery task and the startup warm-up.

Deliberately imports only huggingface_hub (no torch/transformers) so it stays
cheap to import from both predownload.py and tasks_detection_yolo.py.
"""
import logging
import os
from dataclasses import dataclass

from huggingface_hub import hf_hub_download

logger = logging.getLogger(__name__)

# Dev override: uncomment (here and in resolve_yolo_weights below) to run a
# local .pt from this folder instead of the published HF weights.
# LOCAL_YOLO_WEIGHTS = "./argus3_1280_yolo_11x_visdrone960_argus1280.pt"

YOLO_REPO_ID = os.getenv("ARGUS_YOLO_REPO_ID", "RoblabWhGe/ARGUS-YOLO")
YOLO_FILENAME = os.getenv("ARGUS_YOLO_FILENAME", "argus_yolo11x_1280.pt")


@dataclass(frozen=True)
class ModelSpec:
    repo_id: str
    filename: str
    imgsz: int
    run_reid: bool
    # Optional rename of the checkpoint's class names to ARGUS category names
    # (e.g. "Fire" -> "fire" so the configured detection colors apply).
    class_map: dict[str, str] | None = None
    # If set, only detections with these (post-class_map) names are kept.
    keep_classes: frozenset[str] | None = None


MODELS = {
    "argus": ModelSpec(
        repo_id=YOLO_REPO_ID,
        filename=YOLO_FILENAME,
        imgsz=1280,
        run_reid=True,
    ),
    # YOLOv26-S fire/smoke model. Checkpoint classes: fire, other, smoke —
    # already ARGUS-style lowercase ("fire" matches the configured detection
    # color). Field-test verdict: "fire" works, "smoke"/"other" don't — so
    # only "fire" is kept.
    "fire": ModelSpec(
        repo_id="SalahALHaismawi/yolov26-fire-detection",
        filename="best.pt",
        imgsz=1280,
        run_reid=False,
        keep_classes=frozenset({"fire"}),
    ),
    # Tested, not wired into any pipeline:
    # YOLOv26-M wildfire model (classes: smoke, fire) — fires on almost any
    # red object (fire engines...).
    "wildfire": ModelSpec(
        repo_id="odiug77/wildfire-smoke-fire",
        filename="wildfire-smoke-fire.pt",
        imgsz=1280,
        run_reid=False,
    ),
    # YOLOv8-S forest-fire model — weaker than the yolov26 fire model.
    "forestfire": ModelSpec(
        repo_id="touati-kamel/yolov8s-forest-fire-detection",
        filename="model.pt",
        imgsz=960,
        run_reid=False,
    )
}

# Detector pipelines, selected per detection run by the API (the user picks a
# processing mode in the UI; detectors themselves are not user-configurable).
PIPELINES = {
    "objects": ["argus"],
    "fire": ["fire"],
}


def get_pipeline_specs(pipeline: str) -> list[tuple[str, ModelSpec]]:
    """Return the (name, spec) pairs a pipeline runs, in order."""
    if pipeline not in PIPELINES:
        raise ValueError(
            f"Unknown detection pipeline {pipeline!r} — expected one of {sorted(PIPELINES)}"
        )
    return [(name, MODELS[name]) for name in PIPELINES[pipeline]]


def resolve_yolo_weights(spec: ModelSpec) -> str:
    """Return a filesystem path to the YOLO weights for ``spec``.

    Order: HF cache (offline-safe, no etag round-trips) -> download from the
    public HF repo into the persistent hf_cache volume.
    """
    # Dev override, see LOCAL_YOLO_WEIGHTS above:
    # if os.path.isfile(LOCAL_YOLO_WEIGHTS):
    #     return LOCAL_YOLO_WEIGHTS
    try:
        return hf_hub_download(spec.repo_id, filename=spec.filename, local_files_only=True)
    except Exception:
        logger.info(
            "YOLO weights not in local cache — downloading %s/%s",
            spec.repo_id,
            spec.filename,
        )
        return hf_hub_download(spec.repo_id, filename=spec.filename)
