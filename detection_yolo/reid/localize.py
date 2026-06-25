"""Stage 2 — localize each detection bbox in 3D using a COLMAP reconstruction.

Consumes the artifacts the COLMAP worker wrote to ``reports_data/{id}/colmap/``
(``reconstruction.json`` + a point-cloud ``.ply``) and produces, per detection,
a 3D position in the reconstruction's local metric frame (metres):

    { str(detection_id): {"xyz_local": [x,y,z], "method", "low_confidence", "spread_m"} }

A 4-step fallback cascade runs in order until one yields a position:
    (1) primary frustum      most reliable
    (2) dilated frustum      bbox ×1.75               [low_confidence]
    (3) local plane fit      ray ∩ fitted ground plane [low_confidence]
    (4) bilinear GPS         corner interpolation, z=0 [low_confidence]

Detections that can't be localized are simply absent (→ Stage-3 singletons).

Reference: ``colmap_reconstruction_and_localization_ARGUS.md`` §4.
"""
from __future__ import annotations

import json
import logging
import os
import struct

import numpy as np
from scipy.spatial import cKDTree

from . import colmap_geom as geom
from .spatial import gps_to_utm, interpolate_detection_gps

logger = logging.getLogger(__name__)

# --- Stage 2 constants (§4.7) ---
FRUSTUM_MARGIN_PX = 4.0
FRUSTUM_DILATE_FACTOR = 1.75
MIN_POINTS_FOR_OBJECT = 5
NEAREST_DEPTH_QUANTILE = 0.33
LOCAL_PLANE_RADIUS_M = 12.0
LOW_CONFIDENCE_SPREAD = {"human": 3.0, "vehicle": 8.0}
DEFAULT_LOW_CONFIDENCE_SPREAD = 5.0


# --- PLY reader (minimal: ascii + binary_little_endian, xyz only) -----------

def _read_ply_points(path: str) -> np.ndarray:
    """Read vertex XYZ from a PLY file → (N, 3) float64. Ignores colour/normals."""
    with open(path, "rb") as f:
        if f.readline().strip() != b"ply":
            raise ValueError(f"Not a PLY file: {path}")
        fmt = None
        n_verts = 0
        props: list[tuple[str, str]] = []
        in_vertex = False
        while True:
            line = f.readline().strip()
            if line == b"end_header":
                break
            if not line:
                continue
            parts = line.split()
            kw = parts[0]
            if kw == b"format":
                fmt = parts[1].decode()
            elif kw == b"element":
                in_vertex = parts[1] == b"vertex"
                if in_vertex:
                    n_verts = int(parts[2])
            elif kw == b"property" and in_vertex:
                props.append((parts[1].decode(), parts[2].decode()))

        names = [p[1] for p in props]
        xi, yi, zi = names.index("x"), names.index("y"), names.index("z")

        if fmt == "ascii":
            out = np.empty((n_verts, 3), dtype=np.float64)
            for i in range(n_verts):
                vals = f.readline().split()
                out[i] = (float(vals[xi]), float(vals[yi]), float(vals[zi]))
            return out

        # binary_little_endian
        _PLY_FMT = {
            "char": "b", "int8": "b", "uchar": "B", "uint8": "B",
            "short": "h", "int16": "h", "ushort": "H", "uint16": "H",
            "int": "i", "int32": "i", "uint": "I", "uint32": "I",
            "float": "f", "float32": "f", "double": "d", "float64": "d",
        }
        fmt_chars = [_PLY_FMT[t] for t, _ in props]
        struct_fmt = "<" + "".join(fmt_chars)
        size = struct.calcsize(struct_fmt)
        out = np.empty((n_verts, 3), dtype=np.float64)
        for i in range(n_verts):
            row = struct.unpack(struct_fmt, f.read(size))
            out[i] = (row[xi], row[yi], row[zi])
        return out


# --- reconstruction loading --------------------------------------------------

def _build_pose_index(recon: dict) -> dict:
    """{image_name: pose dict} for registered images (K, R_world_cam, centre, …)."""
    poses: dict = {}
    for name, info in recon.get("images", {}).items():
        if not info.get("registered"):
            continue
        cam = info["camera"]
        fx, fy, cx, cy, k1, k2, p1, p2 = geom.unpack_camera_params(cam["model"], cam["params"])
        poses[name] = {
            "K": geom.build_K(fx, fy, cx, cy),
            "intrinsics": (fx, fy, cx, cy, k1, k2, p1, p2),
            "model": cam["model"],
            "R_world_cam": np.asarray(info["R_world_cam_3x3"], float),
            "camera_center": np.asarray(info["camera_center_utm"], float),  # LOCAL frame
            "width": info.get("width", cam.get("width")),
            "height": info.get("height", cam.get("height")),
        }
    return poses


def load_reconstruction(colmap_dir: str):
    """Load (reconstruction dict, point cloud (N,3), pose index) from ``colmap_dir``.

    Returns ``None`` if the reconstruction artifacts are absent/unreadable.
    """
    recon_path = os.path.join(colmap_dir, "reconstruction.json")
    if not os.path.isfile(recon_path):
        return None
    try:
        with open(recon_path) as f:
            recon = json.load(f)
    except (OSError, ValueError) as e:
        logger.warning("[localize] could not read reconstruction.json: %s", e)
        return None

    ply_rel = recon.get("points_ply") or os.path.join("sparse_aligned", "points.ply")
    ply_path = os.path.join(colmap_dir, ply_rel)
    if not os.path.isfile(ply_path):
        # also try the dense cloud
        dense = os.path.join(colmap_dir, "dense", "fused.ply")
        ply_path = dense if os.path.isfile(dense) else ply_path
    try:
        points = _read_ply_points(ply_path)
    except (OSError, ValueError) as e:
        logger.warning("[localize] could not read point cloud %s: %s", ply_path, e)
        points = np.empty((0, 3), dtype=np.float64)

    return recon, points, _build_pose_index(recon)


# --- the cascade -------------------------------------------------------------

def _localize_one(bbox, cat_name, pose, points3d, kdtree):
    """Steps 1–3 (frustum → dilated → plane). Returns (xyz, method, low_conf, spread) or None."""
    x, y, bw, bh = bbox
    corners = np.array([[x, y], [x + bw, y], [x + bw, y + bh], [x, y + bh]], float)
    cu = geom.undistort_by_model(corners, pose)
    u0, v0 = cu.min(0)
    u1, v1 = cu.max(0)
    rect = (u0, v0, u1 - u0, v1 - v0)

    cam_center = pose["camera_center"]
    R_wc = pose["R_world_cam"]
    K = pose["K"]

    alt = max(30.0, float(cam_center[2]))
    if points3d.shape[0] == 0:
        return None
    cand_idx = kdtree.query_ball_point(cam_center[:2], r=3.0 * alt)
    if not cand_idx:
        return None
    cand = points3d[cand_idx]

    def _frustum_centroid(rect_box, dilate, low_conf_force):
        mask = geom.points_inside_frustum(
            cand, cam_center, R_wc, K, rect_box,
            margin_px=FRUSTUM_MARGIN_PX, near=0.1, far=max(10.0, alt * 2.0),
        )
        inside = cand[mask]
        if inside.shape[0] < MIN_POINTS_FOR_OBJECT:
            return None
        # Nadir heuristic: ground/object points are CLOSEST along the optical axis.
        depths = (inside - cam_center) @ R_wc[:, 2]
        if inside.shape[0] >= 10:
            subset = inside[depths <= np.quantile(depths, NEAREST_DEPTH_QUANTILE)]
        else:
            subset = inside
        subset = subset[geom.mad_filter(subset, k=3.0)]
        if subset.shape[0] == 0:
            return None
        centroid = subset.mean(0)
        xy_spread = float(np.linalg.norm(subset[:, :2].std(0)))
        thresh = LOW_CONFIDENCE_SPREAD.get(cat_name, DEFAULT_LOW_CONFIDENCE_SPREAD)
        low_conf = low_conf_force or (xy_spread > thresh)
        return centroid.tolist(), xy_spread, low_conf

    # (1) primary frustum
    res = _frustum_centroid(rect, False, False)
    if res is not None:
        centroid, spread, low_conf = res
        return centroid, "frustum_localized", low_conf, spread

    # (2) dilated frustum (×1.75 about its centre) — always low_confidence
    cx_r, cy_r = u0 + (u1 - u0) / 2, v0 + (v1 - v0) / 2
    dw, dh = (u1 - u0) * FRUSTUM_DILATE_FACTOR, (v1 - v0) * FRUSTUM_DILATE_FACTOR
    rect_d = (cx_r - dw / 2, cy_r - dh / 2, dw, dh)
    res = _frustum_centroid(rect_d, True, True)
    if res is not None:
        centroid, spread, _ = res
        return centroid, "fallback_dilated_frustum", True, spread

    # (3) local plane fit through the bbox centre — always low_confidence
    cx_b, cy_b = bbox[0] + bbox[2] / 2, bbox[1] + bbox[3] / 2
    uv = geom.undistort_by_model(np.array([[cx_b, cy_b]], float), pose)[0]
    origin, direction = geom.pixel_ray(uv, K, R_wc, cam_center)
    dot = (direction / np.linalg.norm(direction)) @ (R_wc[:, 2] / np.linalg.norm(R_wc[:, 2]))
    t_guess = max(10.0, float(cam_center[2]) * (1 + (1.0 - abs(dot))))
    hit_xy = (origin + t_guess * direction)[:2]
    idx = kdtree.query_ball_point(hit_xy, r=LOCAL_PLANE_RADIUS_M)
    if len(idx) >= 8:
        pts = points3d[idx]
        plane = (geom.find_best_local_plane_ransac(pts, hit_xy, LOCAL_PLANE_RADIUS_M, min_inliers=8)
                 if pts.shape[0] > 20 else geom.fit_local_plane(pts, hit_xy, LOCAL_PLANE_RADIUS_M))
        hit = geom.ray_plane_intersection(origin, direction, plane) if plane else None
        if hit is not None:
            return hit.tolist(), "fallback_local_plane", True, None
    return None


def _fallback_bilinear(bbox, img_meta, geo_offset):
    """Step 4 — bilinear GPS interpolation → UTM-local, z=0. Needs corners_gps."""
    corners = img_meta.get("corners_gps")
    w, h = img_meta.get("width"), img_meta.get("height")
    if not corners or not w or not h:
        return None
    lat, lon = interpolate_detection_gps(bbox, w, h, corners)
    e, n = gps_to_utm(lat, lon)
    return [e - geo_offset[0], n - geo_offset[1], 0.0]


def compute_annotation_positions(detections: list[dict], images: dict, colmap_dir: str) -> dict:
    """Localize every detection in 3D using the report's COLMAP reconstruction.

    Args:
        detections: [{"id", "image_id", "bbox":[x,y,w,h], "class_name"}].
        images: {image_id: {"path", "width", "height", "corners_gps"}}.
        colmap_dir: path to ``reports_data/{id}/colmap`` (relative to CWD or absolute).

    Returns the positions dict keyed by ``str(detection_id)`` (see module docstring).
    Empty dict if the reconstruction can't be loaded.
    """
    loaded = load_reconstruction(colmap_dir)
    if loaded is None:
        return {}
    recon, points, poses = loaded
    geo_offset = recon.get("geo_offset", [0.0, 0.0, 0.0])

    kdtree = cKDTree(points[:, :2]) if points.shape[0] else None
    # image_id -> reconstruction image name (= staged basename of the image path)
    name_by_image_id = {
        img_id: os.path.basename(meta["path"])
        for img_id, meta in images.items()
        if meta.get("path")
    }

    positions: dict = {}
    counts: dict = {}
    for d in detections:
        bbox = d["bbox"]
        cat_name = (d.get("class_name") or "").lower()
        img_id = d["image_id"]
        name = name_by_image_id.get(img_id)
        pose = poses.get(name) if name else None

        result = None
        if pose is not None and kdtree is not None:
            result = _localize_one(bbox, cat_name, pose, points, kdtree)

        if result is not None:
            xyz, method, low_conf, spread = result
        else:
            xyz = _fallback_bilinear(bbox, images.get(img_id, {}), geo_offset)
            if xyz is None:
                continue  # truly unlocalizable -> absent -> Stage-3 singleton
            method, low_conf, spread = "fallback_bilinear", True, None

        positions[str(d["id"])] = {
            "xyz_local": [float(v) for v in xyz],
            "method": method,
            "low_confidence": bool(low_conf),
            "spread_m": (float(spread) if spread is not None else None),
        }
        counts[method] = counts.get(method, 0) + 1

    logger.info("[localize] %d/%d detections localized %s",
                len(positions), len(detections), counts)
    return positions
