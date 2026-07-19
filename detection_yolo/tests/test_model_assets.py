"""Tests for the model registry / pipeline selection in model_assets.py.

Network downloads and actual checkpoint loading are covered by live
verification; here we exercise the registry contents, the pipeline lookup,
the keep_classes / class_map contracts used by the Celery task, and the
cache-first resolution order (with hf_hub_download monkeypatched).

Run:  python -m pytest detection_yolo/tests/test_model_assets.py
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

pytest.importorskip("huggingface_hub")

import model_assets  # noqa: E402
from model_assets import MODELS, PIPELINES, ModelSpec, get_pipeline_specs, resolve_yolo_weights  # noqa: E402


def test_pipelines_reference_known_models():
    assert set(PIPELINES) == {"objects", "fire"}
    for names in PIPELINES.values():
        assert names, "pipeline must run at least one model"
        assert all(name in MODELS for name in names)


def test_objects_pipeline_is_argus_with_reid():
    specs = get_pipeline_specs("objects")
    assert [name for name, _ in specs] == ["argus"]
    assert specs[0][1].run_reid is True
    assert specs[0][1].keep_classes is None


def test_fire_pipeline_keeps_only_fire_class_without_reid():
    specs = get_pipeline_specs("fire")
    assert [name for name, _ in specs] == ["fire"]
    spec = specs[0][1]
    assert spec.run_reid is False
    # "fire" must match the configured detection color key (api/app/config.json).
    assert spec.keep_classes == {"fire"}


def test_get_pipeline_specs_rejects_unknown():
    with pytest.raises(ValueError, match="nope"):
        get_pipeline_specs("nope")


def test_keep_classes_filter_contract():
    # Mirrors the filter the Celery task applies to inference annotations.
    spec = MODELS["fire"]
    annotations = [
        {"bbox": [0, 0, 1, 1], "score": 0.9, "category_name": "fire"},
        {"bbox": [0, 0, 1, 1], "score": 0.5, "category_name": "smoke"},
        {"bbox": [0, 0, 1, 1], "score": 0.4, "category_name": "other"},
    ]
    kept = [det for det in annotations if det["category_name"] in spec.keep_classes]
    assert [d["category_name"] for d in kept] == ["fire"]


def test_class_map_rewrite_contract():
    # Mirrors the rewrite the Celery task applies to inference annotations
    # for any future model whose checkpoint names need renaming.
    spec = ModelSpec(repo_id="org/repo", filename="w.pt", imgsz=640,
                     run_reid=False, class_map={"Fire": "fire"})
    annotations = [
        {"bbox": [0, 0, 1, 1], "score": 0.9, "category_name": "Fire"},
        {"bbox": [0, 0, 1, 1], "score": 0.5, "category_name": "unmapped"},
    ]
    for det in annotations:
        det["category_name"] = spec.class_map.get(det["category_name"], det["category_name"])
    assert [d["category_name"] for d in annotations] == ["fire", "unmapped"]


def test_reid_exclusion_filter_contract():
    # Mirrors the predicate run_reid_clustering applies to reid_input
    # detections (which carry class_name): non-reID model classes are dropped,
    # reID model classes stay.
    exclude_classes = {"fire", "smoke", "other"}
    detections = [
        {"image_id": 1, "class_name": "human"},
        {"image_id": 1, "class_name": "fire"},
        {"image_id": 2, "class_name": "vehicle"},
        {"image_id": 2, "class_name": "smoke"},
    ]
    kept = [d for d in detections if d.get("class_name") not in exclude_classes]
    assert [d["class_name"] for d in kept] == ["human", "vehicle"]


def test_resolve_prefers_cache_then_downloads(monkeypatch):
    calls = []

    def fake_download(repo_id, filename, local_files_only=False):
        calls.append(local_files_only)
        if local_files_only:
            raise FileNotFoundError("not cached")
        return f"/cache/{repo_id}/{filename}"

    monkeypatch.setattr(model_assets, "hf_hub_download", fake_download)
    spec = ModelSpec(repo_id="org/repo", filename="w.pt", imgsz=640, run_reid=False)
    assert resolve_yolo_weights(spec) == "/cache/org/repo/w.pt"
    assert calls == [True, False]  # cache-first, then network
