"""DINOv3 embedding of detection crops (reusable).

Turns each detection bounding box into a fixed-length, L2-normalized DINOv3
vector so that cosine similarity later reduces to a plain dot product.

This module is intentionally free of any clustering / spatial logic so it can
be reused by other re-identification strategies. Importing it must **not** load
the model or touch the GPU — the model is loaded lazily on first use and cached.
"""
from __future__ import annotations

import logging
import os
from collections import defaultdict

import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

# Default backbone. Overridable via env or the ``model_id`` arguments below.
#   facebook/dinov3-vitl16-pretrain-lvd1689m   (larger, more GPU RAM)
#   facebook/dinov3-vitl16-pretrain-sat493m    (satellite-pretrained)
DEFAULT_MODEL_ID = os.getenv(
    "HF_REID_MODEL_ID", "facebook/dinov3-vitb16-pretrain-lvd1689m"
)

BBOX_PADDING_RATIO = 0.05
BATCH_SIZE = int(os.getenv("REID_BATCH_SIZE", "32"))

# Keep the model resident between tasks: skips the per-run disk->GPU weight
# load at the cost of permanently held (GPU) memory.
KEEP_MODELS_LOADED = os.getenv("REID_KEEP_MODEL_LOADED", "false").lower() not in (
    "0",
    "false",
    "no",
    "",
)

# model_id -> (processor, model, device)
_MODEL_CACHE: dict[str, tuple] = {}


def get_model(model_id: str = DEFAULT_MODEL_ID):
    """Lazily load and cache the DINOv3 processor + model.

    The first call pulls the model onto the GPU (or CPU); subsequent calls
    return the cached tuple. Kept out of module import on purpose.
    """
    cached = _MODEL_CACHE.get(model_id)
    if cached is not None:
        return cached
    # Local imports keep the module light and avoid importing torch/transformers
    # (and triggering any CUDA init) just by importing this file.
    import torch
    from transformers import AutoImageProcessor, AutoModel

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    logger.info("[reid] loading DINOv3 model %s on %s", model_id, device)
    try:
        # Cached weights only: no HF etag round-trips, works offline.
        processor = AutoImageProcessor.from_pretrained(model_id, local_files_only=True)
        model = AutoModel.from_pretrained(model_id, local_files_only=True)
    except OSError:
        # Cache miss (fresh volume or model switched) — download once into the
        # persistent cache. The gated repo needs HF_TOKEN in the environment,
        # which the Celery task sets from the API payload before calling us.
        logger.info("[reid] %s not in local cache — downloading", model_id)
        processor = AutoImageProcessor.from_pretrained(model_id)
        model = AutoModel.from_pretrained(model_id)
    model = model.eval().to(device)
    _MODEL_CACHE[model_id] = (processor, model, device)
    return processor, model, device


def unload_models() -> None:
    """Drop cached models and free GPU memory (best-effort).

    No-op when REID_KEEP_MODEL_LOADED is set, so repeated tasks skip the
    disk->GPU reload.
    """
    if KEEP_MODELS_LOADED:
        return
    _MODEL_CACHE.clear()
    import gc

    gc.collect()
    try:
        import torch

        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.ipc_collect()
    except ImportError:
        pass


def crop_bbox_rgb(frame_rgb: np.ndarray, bbox_xyxy, padding_ratio: float = BBOX_PADDING_RATIO):
    """Crop ``bbox_xyxy`` from an RGB frame with symmetric padding.

    ``padding_ratio`` of the box width/height is added on each side and clamped
    to the image, giving DINOv3 a little context around the object.
    """
    x1, y1, x2, y2 = bbox_xyxy
    h, w = frame_rgb.shape[:2]
    if x2 <= x1 or y2 <= y1:
        raise ValueError(f"Invalid bbox: {bbox_xyxy}")
    pad_x = int(round((x2 - x1) * padding_ratio))
    pad_y = int(round((y2 - y1) * padding_ratio))
    x1 = max(0, x1 - pad_x)
    y1 = max(0, y1 - pad_y)
    x2 = min(w, x2 + pad_x)
    y2 = min(h, y2 + pad_y)
    return frame_rgb[y1:y2, x1:x2]


def extract_embeddings(crops_rgb, model_id: str = DEFAULT_MODEL_ID, batch_size: int = BATCH_SIZE):
    """Embed a list of RGB crops (HxWx3 uint8 arrays) -> (N, D) float32.

    Vectors are L2-normalized so cosine similarity == dot product. Uses the
    model's ``pooler_output`` (global feature); falls back to mean-pooling the
    patch tokens of ``last_hidden_state`` when a variant doesn't expose it.
    """
    if not crops_rgb:
        return np.empty((0, 0), dtype=np.float32)
    import torch
    import torch.nn.functional as F

    from gpu_batch import run_with_oom_backoff

    processor, model, device = get_model(model_id)

    def _embed_chunk(chunk):
        with torch.inference_mode():
            inputs = processor(images=chunk, return_tensors="pt")
            inputs = {k: v.to(device, non_blocking=True) for k, v in inputs.items()}
            outputs = model(**inputs)
            pooled = getattr(outputs, "pooler_output", None)
            if pooled is None:
                pooled = outputs.last_hidden_state.mean(dim=1)  # mean-pool patch tokens
            emb = F.normalize(pooled.float(), p=2, dim=-1)  # L2-normalize -> cosine = dot
            return list(emb.cpu().numpy())

    # Halves the batch and retries on CUDA OOM instead of failing the reID.
    rows, _ = run_with_oom_backoff(_embed_chunk, crops_rgb, batch_size)
    return np.stack(rows).astype(np.float32)


def embed_detections(
    image_paths: dict,
    dets_by_image: dict,
    model_id: str = DEFAULT_MODEL_ID,
    padding_ratio: float = BBOX_PADDING_RATIO,
    batch_size: int = BATCH_SIZE,
    dump_dir=None,
):
    """Embed every detection crop, reading each image exactly once.

    Args:
        image_paths:   {image_id: absolute/relative path or None}
        dets_by_image: {image_id: [detection dicts with "id" and "bbox"=[x,y,w,h]]}
        dump_dir:      if set, the exact RGB crops fed to DINOv3 are written there
                       (one PNG per detection) plus a manifest.json — for manual
                       inspection / debugging. Existing contents are cleared first.

    Returns:
        {detection_id: (D,) L2-normalized float32}. Degenerate / unreadable
        detections are simply omitted (they become singletons downstream).
    """
    dump_path = None
    manifest: list = []
    if dump_dir:
        import shutil
        from pathlib import Path

        dump_path = Path(dump_dir)
        if dump_path.exists():
            shutil.rmtree(dump_path, ignore_errors=True)
        dump_path.mkdir(parents=True, exist_ok=True)

    crops, crop_ids = [], []
    for img_id, dets in dets_by_image.items():
        path = image_paths.get(img_id)
        if not dets or not path:
            continue
        try:
            frame = np.asarray(Image.open(path).convert("RGB"))
        except Exception as e:  # noqa: BLE001 - unreadable image -> skip its crops
            logger.warning("[reid] could not read image %s: %s", path, e)
            continue
        for d in dets:
            x, y, w, h = d["bbox"]
            if w <= 0 or h <= 0:
                continue
            bbox_xyxy = (
                int(round(x)),
                int(round(y)),
                int(round(x + w)),
                int(round(y + h)),
            )
            try:
                crop = crop_bbox_rgb(frame, bbox_xyxy, padding_ratio)
            except ValueError:
                continue
            if crop.size == 0:
                continue
            crops.append(crop)
            crop_ids.append(d["id"])

            if dump_path is not None:
                cls = d.get("class_name") or "na"
                safe_cls = "".join(c if c.isalnum() else "_" for c in str(cls))
                fname = f"det_{d['id']}_{safe_cls}.png"
                try:
                    Image.fromarray(crop).save(dump_path / fname)
                except Exception as e:  # noqa: BLE001 - dump is best-effort
                    logger.warning("[reid] could not dump crop %s: %s", fname, e)
                manifest.append(
                    {
                        "detection_id": d["id"],
                        "image_id": img_id,
                        "class_name": d.get("class_name"),
                        "bbox": d["bbox"],
                        "crop": fname,
                    }
                )

    if dump_path is not None:
        import json

        try:
            (dump_path / "manifest.json").write_text(json.dumps(manifest, indent=2))
        except Exception as e:  # noqa: BLE001 - dump is best-effort
            logger.warning("[reid] could not write crop manifest: %s", e)
        logger.info("[reid] dumped %d crops to %s", len(manifest), dump_path)

    if not crops:
        return {}
    emb = extract_embeddings(crops, model_id=model_id, batch_size=batch_size)
    return {cid: emb[i] for i, cid in enumerate(crop_ids)}


def grouped_by_image(detections: list[dict]) -> dict:
    """Group detection dicts by their ``image_id`` (stable order preserved)."""
    out: dict = defaultdict(list)
    for d in detections:
        out[d["image_id"]].append(d)
    return out
