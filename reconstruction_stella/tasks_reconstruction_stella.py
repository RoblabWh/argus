from celery import Celery
import os
import logging
import tempfile

import redis
import requests
import yaml
import numpy as np

from stellapy import StellaVSLAM
import cv2 as cv


logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.WARNING)

REDIS_HOST = os.getenv("HOST_REDIS", "redis")
REDIS_PORT = int(os.getenv("PORT_REDIS", 6379))
BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8008")
r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0)

# Celery app for *this* pipeline
celery_app = Celery(
    "reconstruction_stella",
    broker=f"redis://{REDIS_HOST}:{REDIS_PORT}/0",
    backend=f"redis://{REDIS_HOST}:{REDIS_PORT}/0",
)


SCRIPT_PATH = os.path.dirname(os.path.abspath(__file__))
VOCAB_PATH = os.path.join(SCRIPT_PATH, "stella_fbow_vocab", "orb_vocab.fbow")
CONFIG_PATH = os.path.join(SCRIPT_PATH, "config_presets")
CONFIG_PRESETS = {
    os.path.splitext(f)[0]: os.path.join(CONFIG_PATH, f)
    for f in os.listdir(CONFIG_PATH)
    if f.endswith(".yaml")
}


def deep_update(base: dict, override: dict) -> dict:
    """Recursively update override into base. Override values take precedence."""
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            deep_update(base[k], v)
        else:
            base[k] = v
    return base


@celery_app.task(name="reconstruction_stella.run")
def run_reconstruction_stella(
    report_id: int,
    video_path: str,
    results_path: str,
    options: dict = dict(),
    config_overrides: dict = dict(),
):
    logger.info(f"[STELLA] Starting reconstruction for report {report_id}")

    r.set(f"reconstruction:{report_id}:status", "running")
    r.set(f"reconstruction:{report_id}:progress", 0)
    r.set(f"reconstruction:{report_id}:message", "Initializing StellaVSLAM…")

    try:
        # Open video and auto-detect properties
        logger.debug(f"Opening video at path: {video_path}")
        cap = cv.VideoCapture(video_path)
        if not cap.isOpened():
            raise RuntimeError(f"Could not open video: {video_path}")

        frame_step = options.get("frame_step", 1)
        fps = cap.get(cv.CAP_PROP_FPS)
        frame_duration = frame_step / fps
        total_frames = int(cap.get(cv.CAP_PROP_FRAME_COUNT))
        total_steps = max(1, total_frames // frame_step)
        progress_interval = max(1, total_steps // 100)

        config_detected = {
            "Camera": {
                "fps": fps,
                "cols": int(cap.get(cv.CAP_PROP_FRAME_WIDTH)),
                "rows": int(cap.get(cv.CAP_PROP_FRAME_HEIGHT)),
                "color_order": "BGR",
            }
        }
        logger.debug(f"Detected video properties: {config_detected['Camera']}")

        # Load mask if provided
        mask = options.get("mask", np.array([]))
        if isinstance(mask, str):
            mask_path = mask
            logger.debug(f"Loading mask from path: {mask_path}")
            mask = cv.imread(mask_path, cv.IMREAD_GRAYSCALE)
            if mask is None:
                raise RuntimeError(f"Could not read mask image: {mask_path}")
        elif isinstance(mask, np.ndarray):
            logger.debug(f"Mask loaded with shape: {mask.shape}")

        # Build config YAML from preset
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=True
        ) as config_file:
            # Load preset
            preset = options.get("preset", "sparse")
            preset_path = CONFIG_PRESETS.get(preset)
            if preset_path is None:
                raise ValueError(
                    f"Unknown preset '{preset}'. Choose from: {list(CONFIG_PRESETS.keys())}"
                )
            with open(preset_path, "r") as f:
                config = yaml.safe_load(f)
            logger.debug(f"Loaded preset '{preset}' with config: {config}")

            # Apply detected config and user overrides
            deep_update(config, config_detected)
            deep_update(config, config_overrides)

            # Write final config to temp file
            yaml.dump(config, config_file)
            logger.debug(f"Final config written to {config_file.name}:\n{config}")

            # Initialize SLAM
            slam = StellaVSLAM(config_file.name, VOCAB_PATH)
            slam.startup()

            # Process frames
            frame_idx = 0
            while True:
                ok, img = cap.read()
                if not ok:
                    break

                slam.feed_monocular_frame(img, frame_idx * frame_duration, mask)
                frame_idx += 1

                # Skip frames per frame_step
                for _ in range(frame_step - 1):
                    cap.grab()

                # Update progress periodically
                if frame_idx % progress_interval == 0:
                    r.set(
                        f"reconstruction:{report_id}:progress",
                        int((frame_idx / total_steps) * 95),
                    )
                    r.set(
                        f"reconstruction:{report_id}:message",
                        f"Processed {frame_idx} of {total_steps} frames",
                    )

            cap.release()

            r.set(f"reconstruction:{report_id}:progress", 95)
            r.set(f"reconstruction:{report_id}:message", "Finalizing reconstruction…")

            # Shutdown SLAM
            slam.shutdown()

            # Save all outputs
            slam.save_map_database(os.path.join(results_path, "map.db"))
            slam.save_point_cloud(os.path.join(results_path, "sparse.ply"))
            if config["PatchMatch"]["enabled"]:
                slam.save_dense_point_cloud(os.path.join(results_path, "dense.ply"))
            
            r.set(f"reconstruction:{report_id}:progress", 98)
            
            keyframes_dir = os.path.join(results_path, "keyframes")
            os.mkdir(keyframes_dir)
            slam.save_keyframes(keyframes_dir)
            slam.save_frame_trajectory(
                os.path.join(results_path, "frame_trajectory.txt"), "TUM"
            )
            slam.save_keyframe_trajectory(
                os.path.join(results_path, "keyframe_trajectory.txt"), "TUM"
            )

            r.set(f"reconstruction:{report_id}:progress", 100)
            r.set(f"reconstruction:{report_id}:status", "finished")
            r.set(
                f"reconstruction:{report_id}:message",
                "Reconstruction completed successfully",
            )

            # Notify API to finalize DB entry
            try:
                requests.post(
                    f"{BACKEND_URL}/reconstruction/{report_id}/complete",
                    timeout=30,
                )
            except Exception as callback_err:
                logger.warning(f"[STELLA] Callback to API failed: {callback_err}")

    except Exception as e:
        logger.error(e)
        r.set(f"reconstruction:{report_id}:status", "error")
        r.set(f"reconstruction:{report_id}:message", str(e))
        r.set(f"reconstruction:{report_id}:progress", 0)
        raise
