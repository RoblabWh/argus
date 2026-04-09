from celery import Celery
import os
import logging
import shutil
import tempfile

import redis
import requests
import yaml
import numpy as np

from stellapy import StellaVSLAM
import cv2 as cv

from preprocess import check_h264_codec, convert_to_h264, flip_video_180


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


def generate_thumbnails(keyframes_dir: str, thumbnail_dir: str, size=(320, 240)):
    """Generate thumbnails for keyframes."""
    os.makedirs(thumbnail_dir, exist_ok=True)
    for filename in os.listdir(keyframes_dir):
        if filename.lower().endswith((".jpg", ".jpeg", ".png")):
            img_path = os.path.join(keyframes_dir, filename)
            img = cv.imread(img_path)
            if img is not None:
                thumbnail = cv.resize(img, size)
                thumbnail_path = os.path.join(thumbnail_dir, filename)
                cv.imwrite(thumbnail_path, thumbnail)

def preprocess(report_id: int, video_path: str, results_path: str, options: dict):
    try:
        r.set(f"reconstruction:{report_id}:progress", 1)
        r.set(f"reconstruction:{report_id}:message", "Initializing…")
        # Clean up any outputs from a previous run
        shutil.rmtree(os.path.join(results_path, "keyframes"), ignore_errors=True)
        for fname in ["map.db", "sparse.ply", "dense.ply", "keyframe_trajectory.txt", "frame_trajectory.txt"]:
            fpath = os.path.join(results_path, fname)
            if os.path.isfile(fpath):
                os.remove(fpath)

        # Codec normalization: convert HEVC → H.264 in-place for browser compatibility
        r.set(f"reconstruction:{report_id}:message", "Checking video codec…")
        r.set(f"reconstruction:{report_id}:progress", 4)
        if check_h264_codec(video_path):
            r.set(f"reconstruction:{report_id}:message", "Converting video to H.264 (this may take a while)…")
            r.set(f"reconstruction:{report_id}:progress", 5)
            if convert_to_h264(video_path):
                logger.info(f"[STELLA] Video converted to H.264: {video_path}")
            else:
                raise RuntimeError("Video codec conversion failed")
        r.set(f"reconstruction:{report_id}:progress", 50)
        
        # Flip: create a 180°-rotated copy if requested (upside-down camera mounts)
        flip_video = options.get("flip_video", False)
        if flip_video:
            r.set(f"reconstruction:{report_id}:message", "Flipping video 180°…")
            video_path = flip_video_180(video_path)
            # Notify API to update DB video_path to the flipped file.
            # Stella path: /data/reports/{report_id}/video_flipped.mp4
            # API relative path: {report_id}/video_flipped.mp4
            relative_path = "/".join(video_path.split("/")[-2:])
            try:
                requests.post(
                    f"{BACKEND_URL}/reconstruction/{report_id}/set_video_path",
                    json={"video_path": relative_path},
                    timeout=10,
                )
            except Exception as e:
                logger.warning(f"[STELLA] Failed to update video path in DB: {e}")
        r.set(f"reconstruction:{report_id}:progress", 100)
    except Exception as e:
        logger.error(f"[STELLA] Preprocessing error: {e}")
        raise RuntimeError(f"Preprocessing failed: {e}")


@celery_app.task(name="reconstruction_stella.run")
def run_reconstruction_stella(
    report_id: int,
    video_path: str,
    results_path: str,
    options: dict = dict(),
    config_overrides: dict = dict(),
):
    logger.info(f"[STELLA] Starting reconstruction for report {report_id}")

    r.set(f"reconstruction:{report_id}:status", "preprocessing")
    r.set(f"reconstruction:{report_id}:progress", 0)
    r.set(f"reconstruction:{report_id}:message", "Initializing StellaVSLAM…")

    try:
        preprocess(report_id, video_path, results_path, options)
        
        r.set(f"reconstruction:{report_id}:progress", 0)
        r.set(f"reconstruction:{report_id}:status", "processing")
        r.set(f"reconstruction:{report_id}:message", "Initializing StellaVSLAM…")

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
            if config["PatchMatch"]["enabled"]:
                slam.save_point_cloud(os.path.join(results_path, "dense.ply"))

            r.set(f"reconstruction:{report_id}:progress", 98)

            keyframes_dir = os.path.join(results_path, "keyframes")
            os.mkdir(keyframes_dir)
            slam.save_keyframes(keyframes_dir)
            r.set(f"reconstruction:{report_id}:progress", 99)
            generate_thumbnails(keyframes_dir, os.path.join(keyframes_dir, "thumbnails"))
            slam.save_frame_trajectory(
                os.path.join(results_path, "frame_trajectory.txt"), "TUM"
            )
            slam.save_keyframe_trajectory(
                os.path.join(results_path, "keyframe_trajectory.txt"), "TUM"
            )

            r.set(f"reconstruction:{report_id}:progress", 100)
            r.set(f"reconstruction:{report_id}:status", "completed")
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

