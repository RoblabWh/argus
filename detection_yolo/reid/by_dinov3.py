"""DINOv3 appearance re-identification orchestrator ("A4" approach).

Ties the reusable pieces together:

    crops -> DINOv3 embeddings (appearance)
          -> bbox-centre GPS -> UTM (ground position)
          -> per-category KD-tree gate (<= NEIGHBOR_RADIUS_M)
          -> cosine similarity >= SIM_THRESHOLD edges
          -> constrained union-find (no two boxes from one image in a cluster)
          -> {unique_object_id: [detection_id, ...]}

Every input detection id ends up in exactly one cluster list; ids run
contiguously from 1. Detections that cannot be embedded or localized are
emitted as singletons (never lost).
"""
from __future__ import annotations

import logging
import os
from collections import defaultdict

import numpy as np
from scipy.spatial import cKDTree

from . import embeddings as emb_mod
from .clustering import constrained_merge
from .spatial import gps_to_utm, interpolate_detection_gps

logger = logging.getLogger(__name__)

NEIGHBOR_RADIUS_M = float(os.getenv("REID_NEIGHBOR_RADIUS_M", "8.0"))
NEIGHBOR_RADIUS_BY_CATEGORY_M = {
    "default": NEIGHBOR_RADIUS_M,
    "person": float(os.getenv("REID_NEIGHBOR_RADIUS_PERSON_M", "8.0")),
    "vehicle": float(os.getenv("REID_NEIGHBOR_RADIUS_VEHICLE_M", "12.0")),
}
SIM_THRESHOLD = float(os.getenv("REID_SIM_THRESHOLD", "0.72"))


def _category_id_map(detections: list[dict]) -> dict:
    """Build a stable {category -> int} map.

    Detections may already carry an int ``category_id``; otherwise fall back to
    the string ``class_name``. Gating only needs same-vs-different, so any
    stable mapping is fine.
    """
    cats = []
    for d in detections:
        key = d.get("category_id")
        if key is None:
            key = d.get("class_name")
        cats.append(key)
    uniq = {}
    for c in cats:
        if c not in uniq:
            uniq[c] = len(uniq)
    return uniq

def _get_neighbor_radius(category_id: int, cat_map: dict) -> float:
    """Get the neighbor radius for a given category."""
    cat_name = None
    for name, id in cat_map.items():
        if id == category_id:
            cat_name = name
            break
    if cat_name and cat_name in NEIGHBOR_RADIUS_BY_CATEGORY_M:
        return NEIGHBOR_RADIUS_BY_CATEGORY_M[cat_name]
    return NEIGHBOR_RADIUS_BY_CATEGORY_M["default"]


def run_reid(
    detections: list[dict],
    images: dict,
    *,
    model_id: str = emb_mod.DEFAULT_MODEL_ID,
    sim_threshold: float = SIM_THRESHOLD,
    progress_cb=None,
    dump_dir=None,
) -> dict[int, list[int]]:
    """Cluster detections of the same physical object.

    Args:
        detections: [{"id", "image_id", "bbox":[x,y,w,h], "class_name" (and/or
            "category_id")}], iterated in stable order.
        images: {image_id: {"path", "width", "height",
            "corners_gps": [TL,TR,BR,BL] each [lat,lon] | None}}.
        progress_cb: optional callable(message: str, fraction: float in [0,1]).

    Returns:
        {unique_object_id: [detection_id, ...]} covering every input detection.
    """

    def _progress(msg, frac):
        if progress_cb:
            try:
                progress_cb(msg, frac)
            except Exception:  # noqa: BLE001 - progress is best-effort
                pass

    cat_map = _category_id_map(detections)

    # --- Step 1: embed every detection crop (read each image once) ---
    _progress("Embedding detection crops…", 0.05)
    image_paths = {img_id: meta.get("path") for img_id, meta in images.items()}
    dets_by_image = emb_mod.grouped_by_image(detections)
    emb_by_det = emb_mod.embed_detections(
        image_paths, dets_by_image, model_id=model_id, dump_dir=dump_dir
    )

    # --- Step 2: keep detections with BOTH an embedding AND a ground position ---
    _progress("Localizing detections…", 0.55)
    idx_det_ids: list = []
    emb_rows: list = []
    utm_rows: list = []
    image_id_rows: list = []
    category_rows: list = []

    for d in detections:  # stable input order
        emb = emb_by_det.get(d["id"])
        if emb is None:
            continue  # no embedding -> singleton later
        img = images.get(d["image_id"])
        corners = img.get("corners_gps") if img else None
        w = img.get("width") if img else None
        h = img.get("height") if img else None
        if not corners or not w or not h:
            continue  # no georef -> singleton later
        lat, lon = interpolate_detection_gps(
            d["bbox"], w, h, corners, src_px=img.get("corners_src_px")
        )
        e, n = gps_to_utm(lat, lon)
        idx_det_ids.append(d["id"])
        emb_rows.append(emb)
        utm_rows.append([e, n])
        image_id_rows.append(d["image_id"])
        category_rows.append(cat_map[d.get("category_id", d.get("class_name"))])

    n_local = len(idx_det_ids)

    roots: list[int] = []
    if n_local > 0:
        emb = np.vstack(emb_rows).astype(np.float32)  # (N, D) L2-normalized
        utm = np.asarray(utm_rows, dtype=np.float64)  # (N, 2)
        image_ids = np.asarray(image_id_rows)
        category_ids = np.asarray(category_rows)

        # --- Step 3: per-category KD-tree gate + cosine-similarity edges ---
        _progress("Matching appearances…", 0.7)
        edges = []  # (local_i, local_j, cosine_sim)
        for cat in np.unique(category_ids):
            cat_idx = np.flatnonzero(category_ids == cat)
            if cat_idx.size < 2:
                continue
            tree = cKDTree(utm[cat_idx])
            neighbor_radius_m = _get_neighbor_radius(cat, cat_map)
            pairs = tree.query_pairs(r=neighbor_radius_m, output_type="ndarray")
            if pairs.size == 0:
                continue
            gi = cat_idx[pairs[:, 0]]
            gj = cat_idx[pairs[:, 1]]
            sims = np.einsum("ij,ij->i", emb[gi], emb[gj])  # cosine (normalized)
            for a, b, s in zip(gi.tolist(), gj.tolist(), sims.tolist()):
                if s >= sim_threshold:
                    edges.append((a, b, float(s)))

        # --- Steps 4 & 5: constrained union-find merge ---
        _progress("Clustering…", 0.85)
        roots = constrained_merge(edges, image_ids, n_local)

    # --- Step 6: build the output dict (clusters first, then singletons) ---
    _progress("Building object groups…", 0.95)
    root_to_uid: dict = {}
    det_to_uid: dict = {}
    next_id = 1
    for local_i, det_id in enumerate(idx_det_ids):
        r = roots[local_i]
        if r not in root_to_uid:
            root_to_uid[r] = next_id
            next_id += 1
        det_to_uid[det_id] = root_to_uid[r]

    localized = set(idx_det_ids)
    for d in detections:
        if d["id"] not in localized:
            det_to_uid[d["id"]] = next_id
            next_id += 1

    clusters: dict = defaultdict(list)
    for det_id, uid in det_to_uid.items():
        clusters[uid].append(det_id)

    _progress("Re-identification complete.", 1.0)
    logger.info(
        "[reid] %d detections -> %d objects (%d localized)",
        len(detections),
        len(clusters),
        n_local,
    )
    return dict(clusters)
