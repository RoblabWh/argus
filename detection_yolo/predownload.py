"""Container-start model warm-up.

Ensures the DINOv3 re-ID backbone and the YOLO detection weights are present
in the persistent HF cache (the ``hf_cache`` Docker volume) before Celery
starts, so the first detection run never pays a mid-task download.

Never fails the container start: on any error (missing/invalid HF token,
no network, ...) it logs what to do and exits 0 — the lazy loading in
``reid.embeddings.get_model`` retries at task time with whatever HF token
the API passes along then.
"""
import logging
import os
import sys

logging.basicConfig(level=logging.INFO, format="[predownload] %(levelname)s: %(message)s")
logger = logging.getLogger("predownload")

# Weight + config files are enough to run; skips README/license blobs and any
# duplicate .bin weights, and keeps the cache check consistent with what we
# actually download.
DINO_ALLOW_PATTERNS = ["*.json", "*.safetensors"]

GATED_HELP = (
    "DINOv3 weights are license-gated on Hugging Face. To enable re-identification:\n"
    "  1. Create a (free) Hugging Face account\n"
    "  2. Accept the model license on https://huggingface.co/%s\n"
    "  3. Create a read access token (https://huggingface.co/settings/tokens)\n"
    "  4. Set HF_TOKEN in the ARGUS .env or on the ARGUS settings page\n"
    "Detection works without it; only re-identification is skipped until then."
)


def warm_dinov3() -> None:
    from huggingface_hub import snapshot_download

    from reid.embeddings import DEFAULT_MODEL_ID

    try:
        snapshot_download(
            DEFAULT_MODEL_ID, allow_patterns=DINO_ALLOW_PATTERNS, local_files_only=True
        )
        logger.info("DINOv3 weights already cached (%s)", DEFAULT_MODEL_ID)
        return
    except Exception:
        pass

    if not os.getenv("HF_TOKEN"):
        logger.warning("DINOv3 weights not cached and no HF_TOKEN set.")
        logger.warning(GATED_HELP, DEFAULT_MODEL_ID)
        return

    try:
        logger.info("Downloading DINOv3 weights (%s)…", DEFAULT_MODEL_ID)
        snapshot_download(DEFAULT_MODEL_ID, allow_patterns=DINO_ALLOW_PATTERNS)
        logger.info("DINOv3 weights downloaded and cached persistently.")
    except Exception as e:  # noqa: BLE001 - warm-up must never block startup
        logger.warning("Could not download DINOv3 weights (%s): %s", DEFAULT_MODEL_ID, e)
        logger.warning(GATED_HELP, DEFAULT_MODEL_ID)


def warm_yolo() -> None:
    from model_assets import MODELS, PIPELINES, resolve_yolo_weights

    # Warm every model any pipeline can run (deduped, in pipeline order).
    model_names = list(dict.fromkeys(name for names in PIPELINES.values() for name in names))
    for model_name in model_names:
        spec = MODELS[model_name]
        try:
            path = resolve_yolo_weights(spec)
            logger.info("YOLO weights ready (model %s: %s)", model_name, path)
        except Exception as e:  # noqa: BLE001 - warm-up must never block startup
            logger.warning(
                "Could not fetch YOLO weights %s/%s: %s — will retry on the first detection run.",
                spec.repo_id,
                spec.filename,
                e,
            )


if __name__ == "__main__":
    warm_dinov3()
    warm_yolo()
    sys.exit(0)
