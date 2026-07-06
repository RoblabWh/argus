"""Tests for the adaptive GPU batch sizing / OOM backoff helpers.

The CUDA sizing path needs a real GPU and is covered by live verification;
here we exercise the override/CPU paths and the backoff logic with a fake
OOM-raising function (torch.cuda.OutOfMemoryError is instantiable without a
GPU).

Run:  python -m pytest detection_yolo/tests/test_gpu_batch.py
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

torch = pytest.importorskip("torch")

from gpu_batch import adaptive_batch_size, run_with_oom_backoff  # noqa: E402


def test_backoff_halves_and_completes():
    calls = []

    def fn(chunk):
        calls.append(len(chunk))
        if len(chunk) > 2:
            raise torch.cuda.OutOfMemoryError("fake OOM")
        return [x * 10 for x in chunk]

    items = list(range(10))
    results, bs = run_with_oom_backoff(fn, items, 8)
    assert results == [x * 10 for x in items]  # completeness + order
    assert bs == 2  # reduced size is reported back
    assert calls[:2] == [8, 4]  # halving path 8 -> 4 -> 2


def test_backoff_reraises_when_single_item_does_not_fit():
    def fn(chunk):
        raise torch.cuda.OutOfMemoryError("fake OOM")

    with pytest.raises(torch.cuda.OutOfMemoryError):
        run_with_oom_backoff(fn, [1, 2], 2)


def test_backoff_propagates_non_oom_errors():
    def fn(chunk):
        raise ValueError("not an OOM")

    with pytest.raises(ValueError):
        run_with_oom_backoff(fn, [1, 2], 2)


def test_env_override_wins(monkeypatch):
    monkeypatch.setenv("YOLO_BATCH_SIZE", "4")
    assert adaptive_batch_size("cuda:0") == 4
    assert adaptive_batch_size("cpu") == 4


def test_cpu_keeps_max_batch(monkeypatch):
    monkeypatch.delenv("YOLO_BATCH_SIZE", raising=False)
    assert adaptive_batch_size("cpu", max_batch=16) == 16
