"""3D + DINOv3 weighted multi-pass re-identification ("A3B" approach).

The stronger sibling of ``by_dinov3`` (A4): instead of a flat GPS gate, it
clusters on **real 3D positions** (from COLMAP, via :mod:`reid.localize`) whose
distance is *re-weighted by* DINOv3 appearance, merged in strict→loose passes,
with an optional appearance-only cleanup pass.

    scaled_distance = raw_3d_distance * (SIM_FACTOR - cosine_sim)

A detection is *usable* only if it has BOTH a 3D position AND an embedding;
everything else becomes a singleton. One shared constrained union-find enforces
the no-same-image invariant across every pass.

Reference: ``by_3d_dinov3_weighted_multipass_ARGUS.md``.
"""
from __future__ import annotations

import logging
import os
from collections import defaultdict

import numpy as np
from scipy.spatial import cKDTree

from . import embeddings as emb_mod
from .clustering import UnionFind

logger = logging.getLogger(__name__)

# --- constants (§12) ---
SIM_FACTOR = float(os.getenv("REID3D_SIM_FACTOR", "1.6"))
MAX_SIM = 1.0
MIN_FACTOR = max(SIM_FACTOR - MAX_SIM, 1e-6)            # 0.6
SANITY_LEVELS = sorted([0.75, 0.50], reverse=True)     # strict → loose
LOOSEST_GATE = SANITY_LEVELS[-1]

MERGE_THRESHOLD = {
    "human": 2.5,
    "vehicle": 4.0,
    "land_vehicle": 4.0,
    "fire": 1.0,
}
DEFAULT_MERGE_THRESHOLD = 1.0

ENABLE_CLEANUP_PASS = os.getenv("REID3D_CLEANUP", "1").lower() not in ("0", "false", "no", "")
CLEANUP_RADIUS_MULTIPLIER = 10.0
CLEANUP_SMALL_MAX = 3
# The cleanup pass merges on appearance ALONE inside 10x the merge threshold
# (25 m for humans, 40 m for vehicles), so this floor is the only thing keeping
# two different objects apart. DINOv3 cosine between distinct small aerial
# objects routinely reaches 0.65-0.75 — anything below ~0.72 over-merges.
CLEANUP_SANITY_SIM = float(os.getenv("REID3D_CLEANUP_SIM", "0.72"))


# Map raw YOLO/VisDrone class names to the canonical names the thresholds use.
_HUMAN_KEYS = ("human", "person", "people", "pedestrian")
_VEHICLE_KEYS = ("vehicle", "car", "van", "truck", "bus", "motor", "bike",
                 "bicycle", "tricycle", "trailer")


def canonical_category(class_name: str | None) -> str:
    """Lower-cased canonical category for threshold lookup ('human'/'vehicle'/'fire'/…)."""
    name = (class_name or "").lower()
    if any(k in name for k in _HUMAN_KEYS):
        return "human"
    if "fire" in name:
        return "fire"
    if any(k in name for k in _VEHICLE_KEYS):
        return "vehicle"
    return name


def _threshold_for(cat_name: str) -> float:
    return MERGE_THRESHOLD.get(cat_name, DEFAULT_MERGE_THRESHOLD)


def run_reid_3d(
    detections: list[dict],
    images: dict,
    positions: dict,
    *,
    model_id: str = emb_mod.DEFAULT_MODEL_ID,
    progress_cb=None,
    dump_dir=None,
) -> dict[int, list[int]]:
    """Cluster detections of the same physical object using 3D positions + appearance.

    Args:
        detections: [{"id", "image_id", "bbox":[x,y,w,h], "class_name"}].
        images: {image_id: {"path", "width", "height", ...}} (embedding reads "path").
        positions: {str(detection_id): {"xyz_local":[x,y,z], ...}} from Stage 2.
        progress_cb: optional callable(message:str, fraction:float in [0,1]).

    Returns:
        {unique_object_id: [detection_id, ...]} covering every input detection;
        ids contiguous from 1.
    """

    def _progress(msg, frac):
        if progress_cb:
            try:
                progress_cb(msg, frac)
            except Exception:  # noqa: BLE001 - progress is best-effort
                pass

    # --- Step 1: embed every detection crop (reuse the A4 embedding code) ---
    _progress("Embedding detection crops…", 0.05)
    image_paths = {img_id: meta.get("path") for img_id, meta in images.items()}
    dets_by_image = emb_mod.grouped_by_image(detections)
    emb_by_det = emb_mod.embed_detections(
        image_paths, dets_by_image, model_id=model_id, dump_dir=dump_dir
    )

    # --- Step 2: keep detections with BOTH a 3D position AND an embedding ---
    _progress("Joining 3D positions with appearance…", 0.6)
    usable_ids: list = []
    pts_rows: list = []
    emb_rows: list = []
    image_id_row: list = []
    category_row: list = []

    for d in detections:  # stable input order
        rec = positions.get(str(d["id"]))
        xyz = rec.get("xyz_local") if rec else None
        e = emb_by_det.get(d["id"])
        if xyz is not None and e is not None:
            usable_ids.append(d["id"])
            pts_rows.append(xyz)
            emb_rows.append(e)
            image_id_row.append(d["image_id"])
            category_row.append(canonical_category(d.get("class_name")))

    n = len(usable_ids)
    roots: list = []
    if n > 0:
        pts = np.asarray(pts_rows, dtype=np.float64)        # (N, 3) metres, local frame
        emb = np.vstack(emb_rows).astype(np.float32)        # (N, D) L2-normalized
        image_ids = np.asarray(image_id_row)
        categories = np.asarray(category_row, dtype=object)

        uf = UnionFind(n)
        cluster_images = {i: {int(image_ids[i])} for i in range(n)}

        def try_merge(a: int, b: int):
            """Union local a,b honoring no-same-image. Returns cosine sim or None."""
            if image_ids[a] == image_ids[b]:
                return None
            ra, rb = uf.find(a), uf.find(b)
            if ra == rb:
                return None
            if cluster_images[ra] & cluster_images[rb]:
                return None
            new_root = uf.union(ra, rb)
            cluster_images[new_root] = cluster_images[ra] | cluster_images[rb]
            old_root = rb if new_root == ra else ra
            cluster_images.pop(old_root, None)
            return float(np.dot(emb[a], emb[b]))

        # --- Step 3: per-category candidate generation (generous radius) ---
        _progress("Generating 3D candidates…", 0.72)
        edges = []  # (scaled_distance, cosine_sim, a, b)
        for cat in np.unique(categories):
            cat_idx = np.flatnonzero(categories == cat)
            if cat_idx.size < 2:
                continue
            cutoff = _threshold_for(str(cat))
            search_radius = cutoff / MIN_FACTOR
            tree = cKDTree(pts[cat_idx])
            local = tree.query_pairs(r=search_radius, output_type="ndarray")
            if local.size == 0:
                continue
            gi = cat_idx[local[:, 0]]
            gj = cat_idx[local[:, 1]]
            sims = np.einsum("ij,ij->i", emb[gi], emb[gj])      # cosine
            raws = np.linalg.norm(pts[gi] - pts[gj], axis=1)    # 3D distance, metres
            scaled = raws * (SIM_FACTOR - sims)
            for a, b, s, sc in zip(gi.tolist(), gj.tolist(), sims.tolist(), scaled.tolist()):
                if sc > cutoff:
                    continue
                if s < LOOSEST_GATE:
                    continue
                edges.append((sc, s, a, b))

        # --- Step 4: multi-pass gated merge (strict → loose) ---
        _progress("Clustering (multi-pass)…", 0.82)
        for level in SANITY_LEVELS:
            pass_edges = [e for e in edges if e[1] >= level]
            pass_edges.sort(key=lambda e: e[0])              # ascending scaled distance
            for _sc, _s, a, b in pass_edges:
                try_merge(a, b)

        # --- Step 5: optional appearance-only cleanup pass ---
        if ENABLE_CLEANUP_PASS:
            _progress("Cleanup pass…", 0.9)
            roots_before = [uf.find(i) for i in range(n)]
            size_by_root: dict = {}
            for rt in roots_before:
                size_by_root[rt] = size_by_root.get(rt, 0) + 1
            is_small = np.array(
                [size_by_root[roots_before[i]] <= CLEANUP_SMALL_MAX for i in range(n)]
            )
            cleanup_edges = []  # (sim, a, b)
            for cat in np.unique(categories):
                cat_idx = np.flatnonzero(categories == cat)
                if cat_idx.size < 2:
                    continue
                radius = CLEANUP_RADIUS_MULTIPLIER * _threshold_for(str(cat))
                tree = cKDTree(pts[cat_idx])
                local = tree.query_pairs(r=radius, output_type="ndarray")
                if local.size == 0:
                    continue
                gi = cat_idx[local[:, 0]]
                gj = cat_idx[local[:, 1]]
                sims = np.einsum("ij,ij->i", emb[gi], emb[gj])
                for a, b, s in zip(gi.tolist(), gj.tolist(), sims.tolist()):
                    if not (is_small[a] or is_small[b]):
                        continue
                    if s < CLEANUP_SANITY_SIM:
                        continue
                    cleanup_edges.append((s, a, b))
            cleanup_edges.sort(key=lambda e: -e[0])           # best appearance first
            for _s, a, b in cleanup_edges:
                try_merge(a, b)

        roots = [uf.find(i) for i in range(n)]

    # --- Step 6: build the output dict (clusters first, then singletons) ---
    _progress("Building object groups…", 0.96)
    root_to_uid: dict = {}
    det_to_uid: dict = {}
    next_id = 1
    for local_i, det_id in enumerate(usable_ids):
        rt = roots[local_i]
        if rt not in root_to_uid:
            root_to_uid[rt] = next_id
            next_id += 1
        det_to_uid[det_id] = root_to_uid[rt]

    usable_set = set(usable_ids)
    for d in detections:  # singletons: no 3D position OR no embedding
        if d["id"] not in usable_set:
            det_to_uid[d["id"]] = next_id
            next_id += 1

    clusters: dict = defaultdict(list)
    for det_id, uid in det_to_uid.items():
        clusters[uid].append(det_id)

    _progress("Re-identification complete.", 1.0)
    logger.info(
        "[reid3d] %d detections -> %d objects (%d usable in 3D)",
        len(detections), len(clusters), n,
    )
    return dict(clusters)
