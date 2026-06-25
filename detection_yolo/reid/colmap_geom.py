"""Pure-numpy geometry primitives for 3D annotation localization.

No pycolmap / COLMAP dependency — these operate on plain arrays and transfer
verbatim from the dev tool. Camera convention is COLMAP's: +X right, +Y down,
+Z forward; ``R_world_cam`` rotates camera→world.

Reference: ``colmap_reconstruction_and_localization_ARGUS.md`` §4.0–4.1.
"""
from __future__ import annotations

import numpy as np


# --- intrinsics --------------------------------------------------------------

def unpack_camera_params(model: str, params):
    """→ (fx, fy, cx, cy, k1, k2, p1, p2). COLMAP param order is model-specific."""
    params = list(params)
    m = (model or "").upper()
    if m == "OPENCV":          # [fx, fy, cx, cy, k1, k2, p1, p2]
        fx, fy, cx, cy, k1, k2, p1, p2 = (params + [0.0] * 8)[:8]
        return fx, fy, cx, cy, k1, k2, p1, p2
    if m == "SIMPLE_RADIAL":   # [f, cx, cy, k1]
        f, cx, cy, k1 = (params + [0.0] * 4)[:4]
        return f, f, cx, cy, k1, 0.0, 0.0, 0.0
    if m == "SIMPLE_PINHOLE":  # [f, cx, cy]
        f, cx, cy = (params + [0.0] * 3)[:3]
        return f, f, cx, cy, 0.0, 0.0, 0.0, 0.0
    # PINHOLE (our default): [fx, fy, cx, cy]
    fx, fy, cx, cy = (params + [0.0] * 4)[:4]
    return fx, fy, cx, cy, 0.0, 0.0, 0.0, 0.0


def build_K(fx, fy, cx, cy):
    return np.array([[fx, 0, cx], [0, fy, cy], [0, 0, 1.0]])


# --- distortion --------------------------------------------------------------

def undistort_simple_radial(uv, cx, cy, f, k1, iters: int = 5):
    """Invert SIMPLE_RADIAL distortion (Newton iterations)."""
    uv = np.asarray(uv, float).reshape(-1, 2)
    x_d = (uv[:, 0] - cx) / f
    y_d = (uv[:, 1] - cy) / f
    x_u, y_u = x_d.copy(), y_d.copy()
    for _ in range(iters):
        r2 = x_u * x_u + y_u * y_u
        fac = 1.0 + k1 * r2
        x_u, y_u = x_d / fac, y_d / fac
    return np.stack([x_u * f + cx, y_u * f + cy], axis=1)


def undistort_opencv(uv, cx, cy, fx, fy, k1, k2, p1, p2, iters: int = 5):
    """Invert OPENCV (radial k1,k2 + tangential p1,p2) distortion."""
    uv = np.asarray(uv, float).reshape(-1, 2)
    x_d = (uv[:, 0] - cx) / fx
    y_d = (uv[:, 1] - cy) / fy
    x_u, y_u = x_d.copy(), y_d.copy()
    for _ in range(iters):
        r2 = x_u * x_u + y_u * y_u
        radial = 1.0 + k1 * r2 + k2 * r2 * r2
        dx = 2 * p1 * x_u * y_u + p2 * (r2 + 2 * x_u * x_u)
        dy = p1 * (r2 + 2 * y_u * y_u) + 2 * p2 * x_u * y_u
        x_u = (x_d - dx) / radial
        y_u = (y_d - dy) / radial
    return np.stack([x_u * fx + cx, y_u * fy + cy], axis=1)


def undistort_by_model(uv, pose: dict):
    """Dispatch undistortion on the camera model carried by ``pose``."""
    model = (pose.get("model") or "PINHOLE").upper()
    fx, fy, cx, cy, k1, k2, p1, p2 = pose["intrinsics"]
    if model == "SIMPLE_RADIAL":
        return undistort_simple_radial(uv, cx, cy, fx, k1)
    if model == "OPENCV":
        return undistort_opencv(uv, cx, cy, fx, fy, k1, k2, p1, p2)
    # PINHOLE / SIMPLE_PINHOLE — no distortion.
    return np.asarray(uv, float).reshape(-1, 2)


# --- frustum / depth ---------------------------------------------------------

def points_inside_frustum(points_world, camera_center, R_world_cam, K, bbox_xywh,
                          margin_px: float = 4.0, near: float = 0.1, far: float = 500.0):
    """Boolean mask of world points projecting into the (padded) bbox, depth in [near,far]."""
    P = np.asarray(points_world, float)
    C = np.asarray(camera_center, float)
    R_cw = np.asarray(R_world_cam, float).T
    in_cam = (R_cw @ (P - C).T).T                 # world → camera
    z = in_cam[:, 2]
    valid = (z > near) & (z < far)
    proj = (np.asarray(K, float) @ in_cam.T).T
    u = proj[:, 0] / np.where(z == 0, 1, z)
    v = proj[:, 1] / np.where(z == 0, 1, z)
    x, y, w, h = bbox_xywh
    in_bbox = (u >= x - margin_px) & (u <= x + w + margin_px) & \
              (v >= y - margin_px) & (v <= y + h + margin_px)
    return valid & in_bbox


def mad_filter(points, k: float = 3.0):
    """Inlier mask: per-axis deviation from the median within k·MAD. All-True for n ≤ 3."""
    pts = np.asarray(points, float)
    n = pts.shape[0]
    if n <= 3:
        return np.ones(n, bool)
    med = np.median(pts, axis=0)
    dev = np.abs(pts - med)
    mad = np.median(dev, axis=0)
    mad = np.where(mad < 1e-9, 1e-9, mad)
    return np.all(dev / mad < k, axis=1)


# --- rays / planes -----------------------------------------------------------

def pixel_ray(uv, K, R_world_cam, camera_center):
    """World-space ray (origin, unit direction) through pixel (u, v)."""
    cam_dir = np.linalg.inv(K) @ np.array([float(uv[0]), float(uv[1]), 1.0])
    d = np.asarray(R_world_cam, float) @ cam_dir
    return np.asarray(camera_center, float), d / np.linalg.norm(d)


def fit_plane_least_squares(points):
    """Plane (normal, d, centroid) with normal·x + d = 0, normal pointing up (SVD)."""
    pts = np.asarray(points, float)
    centroid = pts.mean(axis=0)
    _, _, Vt = np.linalg.svd(pts - centroid, full_matrices=False)
    normal = Vt[-1]
    if normal[2] < 0:
        normal = -normal
    return normal, float(-normal @ centroid), centroid


def ray_plane_intersection(origin, direction, plane):
    """Intersect ray origin+t·dir (t>0) with plane (n·x+d=0). None if parallel/behind."""
    n, d, _ = plane
    denom = float(np.asarray(n) @ np.asarray(direction))
    if abs(denom) < 1e-9:
        return None
    t = -(float(np.asarray(n) @ np.asarray(origin)) + d) / denom
    return None if t <= 0 else np.asarray(origin, float) + t * np.asarray(direction, float)


def fit_local_plane(points, center_xy, radius):
    """Least-squares plane over points within ``radius`` of ``center_xy`` (XY)."""
    pts = np.asarray(points, float)
    if pts.shape[0] < 3:
        return None
    return fit_plane_least_squares(pts)


def find_best_local_plane_ransac(points, center_xy, radius, min_inliers: int = 8,
                                 iters: int = 100, thresh: float = 0.05):
    """RANSAC plane fit (100 iters, 0.05 m inlier threshold)."""
    pts = np.asarray(points, float)
    n = pts.shape[0]
    if n < 3:
        return None
    rng = np.random.default_rng(0)
    best_inliers = None
    best_count = -1
    for _ in range(iters):
        idx = rng.choice(n, size=3, replace=False)
        try:
            normal, d, _ = fit_plane_least_squares(pts[idx])
        except np.linalg.LinAlgError:
            continue
        dist = np.abs(pts @ normal + d)
        inliers = dist < thresh
        c = int(inliers.sum())
        if c > best_count:
            best_count, best_inliers = c, inliers
    if best_inliers is None or best_count < min_inliers:
        return fit_local_plane(pts, center_xy, radius)
    return fit_plane_least_squares(pts[best_inliers])
