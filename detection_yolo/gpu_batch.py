"""Adaptive GPU batch sizing + CUDA-OOM backoff for inference.

The GPU micro-batch is derived from the *free* VRAM at inference time (the
mapping/ollama workers share the GPU, so total VRAM would overestimate), and
``run_with_oom_backoff`` halves the batch and retries if a forward pass still
runs out of memory.

Calibration (RTX 5080, 15.5 GiB, YOLO11x @ imgsz 1280, 4000x3000 inputs,
measured 2026-07-05) — peak reserved VRAM is nearly linear in batch size,
``peak ~= 0.35 + 0.63 * batch`` GiB:

    batch  1:  0.96 GiB   ( 6% of total)
    batch  4:  2.75 GiB   (18%)
    batch  8:  5.22 GiB   (34%)
    batch 16: 10.71 GiB   (69%)
"""
import logging
import os

logger = logging.getLogger(__name__)

# Fraction of *free* VRAM the micro-batch may target. On an otherwise idle
# 16 GiB card this reproduces the hand-tuned batch of 16 (~69% of total).
TARGET_FRACTION = float(os.getenv("GPU_MEM_TARGET_FRACTION", "0.75"))
BASE_GIB = 0.5        # model + CUDA context headroom
PER_IMAGE_GIB = 0.63  # measured slope, see calibration table above


def adaptive_batch_size(device, max_batch: int = 16) -> int:
    """Pick a YOLO inference micro-batch size for ``device``.

    ``YOLO_BATCH_SIZE`` env forces a fixed size (no adaptation). CPU devices
    keep ``max_batch`` (RAM-bound, unchanged behavior). On CUDA the size is
    computed from currently free VRAM via the calibration constants.
    """
    override = os.getenv("YOLO_BATCH_SIZE")
    if override:
        return max(1, int(override))

    if "cuda" not in str(device):
        return max_batch

    import torch

    if not torch.cuda.is_available():
        return max_batch
    try:
        free_bytes, _total = torch.cuda.mem_get_info()
    except Exception as e:  # noqa: BLE001 - sizing must never break inference
        logger.warning("Could not query free VRAM (%s) — using max_batch %d", e, max_batch)
        return max_batch

    free_gib = free_bytes / 2**30
    batch = int((TARGET_FRACTION * free_gib - BASE_GIB) / PER_IMAGE_GIB)
    batch = max(1, min(batch, max_batch))
    logger.info(
        "Adaptive GPU batch: %d (%.1f GiB free, target fraction %.2f)",
        batch,
        free_gib,
        TARGET_FRACTION,
    )
    return batch


def run_with_oom_backoff(fn, items: list, batch_size: int):
    """Apply ``fn`` to ``items`` in chunks, halving the chunk size on CUDA OOM.

    ``fn`` takes a list chunk and returns a list of per-item results (same
    length, same order). Returns ``(results, effective_batch_size)`` so the
    caller can keep a reduced size for subsequent calls. Re-raises when even
    a single item does not fit.
    """
    results = []
    bs = max(1, batch_size)
    i = 0
    while i < len(items):
        chunk = items[i : i + bs]
        try:
            results.extend(fn(chunk))
            i += len(chunk)
        except Exception as e:
            if not _is_cuda_oom(e):
                raise
            if bs == 1:
                raise
            bs = max(1, bs // 2)
            logger.warning("CUDA OOM at batch %d — retrying with batch %d", len(chunk), bs)
            import torch

            torch.cuda.empty_cache()
    return results, bs


def _is_cuda_oom(exc: Exception) -> bool:
    import torch

    return isinstance(exc, torch.cuda.OutOfMemoryError)
