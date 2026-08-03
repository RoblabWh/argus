"""Verification of the 3D localization + 3D-weighted-multipass reID.

Runs without torch/transformers/pyproj installed: pyproj is stubbed with a
simple local equirectangular projection and the DINOv3 embedding step is
monkeypatched with crafted unit vectors, so the geometry + clustering logic is
exercised deterministically.

Run:  python -m pytest detection_yolo/tests/test_3d_reid.py
  or:  python detection_yolo/tests/test_3d_reid.py
"""
import json
import math
import os
import sys
import tempfile
import types
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _install_pyproj_stub():
    if "pyproj" in sys.modules:
        return
    pyproj = types.ModuleType("pyproj")

    class _T:
        @staticmethod
        def from_crs(src, dst, always_xy=False):
            return _T()

        def transform(self, lat, lon):
            e = lon * 111320.0 * math.cos(math.radians(lat))
            n = lat * 111320.0
            return e, n

    pyproj.Transformer = _T
    sys.modules["pyproj"] = pyproj


_install_pyproj_stub()

from reid import colmap_geom as geom  # noqa: E402
from reid import localize  # noqa: E402
from reid import by_3d_dinov3 as r3d  # noqa: E402
from reid import embeddings  # noqa: E402


# A nadir camera 50 m up looking straight down. Camera convention +X right,
# +Y down, +Z forward; R_world_cam maps camera→world so forward → world -Z.
_R_WORLD_CAM = [[1.0, 0.0, 0.0], [0.0, -1.0, 0.0], [0.0, 0.0, -1.0]]
_CAM_CENTER = [0.0, 0.0, 50.0]
_K_PARAMS = [1000.0, 1000.0, 500.0, 500.0]  # fx, fy, cx, cy


# ---------------------------------------------------------------------------
# colmap_geom primitives
# ---------------------------------------------------------------------------

def test_frustum_selects_only_in_bbox_points():
    K = geom.build_K(*_K_PARAMS)
    C = np.asarray(_CAM_CENTER)
    R = np.asarray(_R_WORLD_CAM)
    pts = np.array([[5.0, 3.0, 1.5],     # projects to ~(607,438) — inside
                    [50.0, 50.0, 0.0]])  # projects far outside the image
    mask = geom.points_inside_frustum(pts, C, R, K, (580, 420, 40, 40),
                                      margin_px=4.0, near=0.1, far=200.0)
    assert mask.tolist() == [True, False]


def test_ray_plane_intersection_hits_ground():
    plane = ([0.0, 0.0, 1.0], 0.0, [0, 0, 0])     # z = 0
    hit = geom.ray_plane_intersection([0, 0, 50], [0, 0, -1], plane)
    assert hit is not None and abs(hit[2]) < 1e-9


def test_mad_filter_rejects_outlier():
    # Inliers must have a non-degenerate spread, else the MAD collapses to ~0
    # and even tiny deviations get flagged (documented behaviour).
    pts = np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0], [1, 1, 0],
                    [100, 100, 100]], float)
    mask = geom.mad_filter(pts, k=3.0)
    assert mask[-1] == False and mask[:4].all()  # noqa: E712


# ---------------------------------------------------------------------------
# Stage 2 — localization (PLY + reconstruction.json on disk)
# ---------------------------------------------------------------------------

def _write_scene(colmap_dir, extra_points=None):
    """A reconstruction with one nadir image + a planted object cluster cloud."""
    os.makedirs(os.path.join(colmap_dir, "sparse_aligned"), exist_ok=True)
    recon = {
        "source": "colmap", "utm_epsg": "EPSG:32632",
        "geo_offset": [0.0, 0.0, 0.0], "reconstruction_mode": "sparse",
        "registered_images": 1, "total_images": 1,
        "points_ply": "sparse_aligned/points.ply",
        "images": {
            "img1.jpg": {
                "image_id": 1, "registered": True,
                "camera_center_utm": _CAM_CENTER,
                "R_world_cam_3x3": _R_WORLD_CAM,
                "camera": {"model": "PINHOLE", "params": _K_PARAMS,
                           "width": 1000, "height": 1000},
                "width": 1000, "height": 1000,
            }
        },
    }
    with open(os.path.join(colmap_dir, "reconstruction.json"), "w") as f:
        json.dump(recon, f)

    rng = np.random.default_rng(0)
    obj = np.column_stack([5.0 + rng.normal(0, 0.05, 12),
                           3.0 + rng.normal(0, 0.05, 12),
                           np.full(12, 1.5)])                  # the object, z≈1.5
    # Ground well outside the bbox frustum. Enough of it that the terrain
    # estimate (a low quantile of z) lands on z=0 rather than on the object,
    # which is what a real aerial cloud looks like.
    far = np.vstack([
        np.column_stack([50.0 + rng.normal(0, 0.5, 6),
                         50.0 + rng.normal(0, 0.5, 6),
                         np.zeros(6)]),
        np.column_stack([-40.0 + rng.normal(0, 0.5, 6),
                         30.0 + rng.normal(0, 0.5, 6),
                         np.zeros(6)]),
    ])
    pts = np.vstack([obj, far])
    if extra_points is not None:
        pts = np.vstack([pts, np.asarray(extra_points, float)])
    ply = os.path.join(colmap_dir, "sparse_aligned", "points.ply")
    with open(ply, "w") as f:
        f.write("ply\nformat ascii 1.0\n")
        f.write(f"element vertex {len(pts)}\n")
        f.write("property float x\nproperty float y\nproperty float z\nend_header\n")
        for p in pts:
            f.write(f"{p[0]:.6f} {p[1]:.6f} {p[2]:.6f}\n")


def test_ply_reader_ascii():
    with tempfile.TemporaryDirectory() as d:
        _write_scene(d)
        pts = localize._read_ply_points(os.path.join(d, "sparse_aligned", "points.ply"))
        assert pts.shape == (24, 3)          # 12 object + 12 ground
        assert localize.estimate_ground_z(pts) == 0.0


def test_localize_frustum_returns_planted_object():
    with tempfile.TemporaryDirectory() as d:
        _write_scene(d)
        detections = [{"id": 101, "image_id": 1, "bbox": [580, 420, 40, 40],
                       "class_name": "human"}]
        images = {1: {"path": "/x/img1.jpg", "width": 1000, "height": 1000,
                      "corners_gps": None}}
        positions = localize.compute_annotation_positions(detections, images, d)
        assert "101" in positions
        rec = positions["101"]
        assert rec["method"] == "frustum_localized"
        xyz = rec["xyz_local"]
        assert abs(xyz[0] - 5.0) < 0.5 and abs(xyz[1] - 3.0) < 0.5
        assert abs(xyz[2] - 1.5) < 0.5          # z is real, not zeroed
        assert rec["low_confidence"] is False


def test_localize_bilinear_fallback_when_unregistered():
    with tempfile.TemporaryDirectory() as d:
        _write_scene(d)
        # image_id 2 is not in the reconstruction -> bilinear fallback path.
        corners = [[50.0010, 7.0000], [50.0010, 7.0010],
                   [50.0000, 7.0010], [50.0000, 7.0000]]
        detections = [{"id": 202, "image_id": 2, "bbox": [400, 400, 20, 20],
                       "class_name": "human"}]
        images = {2: {"path": "/x/img2.jpg", "width": 1000, "height": 1000,
                      "corners_gps": corners}}
        positions = localize.compute_annotation_positions(detections, images, d)
        assert positions["202"]["method"] == "fallback_bilinear"
        assert positions["202"]["xyz_local"][2] == 0.0   # ground plane


def test_localize_registered_fallback_uses_pose_footprint():
    """A registered image whose frustum + plane fit both fail still lands in the
    reconstruction's own frame — not in the mapping pipeline's corners_gps."""
    with tempfile.TemporaryDirectory() as d:
        _write_scene(d)
        # Empty image region: no cloud points project into it, and none lie
        # within the plane-fit radius of the ray's ground hit.
        detections = [{"id": 303, "image_id": 1, "bbox": [100, 100, 20, 20],
                       "class_name": "human"}]
        # corners_gps is None — pre-fix this detection had no position at all.
        images = {1: {"path": "/x/img1.jpg", "width": 1000, "height": 1000,
                      "corners_gps": None}}
        positions = localize.compute_annotation_positions(detections, images, d)
        assert "303" in positions
        xyz = positions["303"]["xyz_local"]
        # Nadir camera 50 m up, f=1000: pixel (110,110) -> ground (-19.5, 19.5).
        assert abs(xyz[0] - (-19.5)) < 0.1
        assert abs(xyz[1] - 19.5) < 0.1
        assert xyz[2] == 0.0


def test_localize_reaches_plane_fit_when_frustum_empty():
    """The plane fit must stay reachable after the cascade restructure."""
    with tempfile.TemporaryDirectory() as d:
        # A ground patch ~6 m around the ray hit of pixel (110,110): far enough
        # from the bbox to stay out of both frustum passes, close enough to be
        # inside LOCAL_PLANE_RADIUS_M.
        ang = np.linspace(0, 2 * np.pi, 12, endpoint=False)
        patch = np.column_stack([-19.2 + 6.0 * np.cos(ang),
                                 19.2 + 6.0 * np.sin(ang),
                                 np.zeros(12)])
        _write_scene(d, extra_points=patch)
        detections = [{"id": 404, "image_id": 1, "bbox": [100, 100, 20, 20],
                       "class_name": "human"}]
        images = {1: {"path": "/x/img1.jpg", "width": 1000, "height": 1000,
                      "corners_gps": None}}
        positions = localize.compute_annotation_positions(detections, images, d)
        assert positions["404"]["method"] == "fallback_local_plane"
        xyz = positions["404"]["xyz_local"]
        assert abs(xyz[0] - (-19.5)) < 0.5 and abs(xyz[1] - 19.5) < 0.5


def test_estimate_ground_z_ignores_raised_structures():
    """Terrain must come from the cloud, not from a z=0 assumption — Stage 1
    leaves altitudes in whichever EXIF datum the flight carried."""
    rng = np.random.default_rng(1)
    # Terrain 250 m up (absolute MSL datum) with a 10 m building on top.
    terrain = np.column_stack([rng.uniform(-50, 50, 400), rng.uniform(-50, 50, 400),
                               np.full(400, 250.0)])
    roof = np.column_stack([rng.uniform(0, 5, 60), rng.uniform(0, 5, 60),
                            np.full(60, 260.0)])
    assert abs(localize.estimate_ground_z(np.vstack([terrain, roof])) - 250.0) < 0.5
    assert localize.estimate_ground_z(np.empty((0, 3))) == 0.0


def test_interpolate_honours_lower_half_src_px():
    """Corners traced from the image's lower half must be normalized against
    that half, not the full frame."""
    from reid.spatial import interpolate_detection_gps

    corners = [[1.0, 0.0], [1.0, 1.0], [0.0, 1.0], [0.0, 0.0]]  # TL, TR, BR, BL
    # bbox centre at 3/4 of the full height = the middle of the lower half.
    bbox = [400, 700, 200, 100]
    full = interpolate_detection_gps(bbox, 1000, 1000, corners)
    half = interpolate_detection_gps(bbox, 1000, 1000, corners,
                                     src_px=[0, 500, 1000, 1000])
    assert abs(full[0] - 0.25) < 1e-9      # lat interpolates 1 -> 0 over v
    assert abs(half[0] - 0.50) < 1e-9      # v = 0.5 inside the lower half
    assert abs(full[1] - 0.50) < 1e-9      # horizontal is unaffected
    assert abs(half[1] - 0.50) < 1e-9


def test_load_reconstruction_missing_returns_none():
    with tempfile.TemporaryDirectory() as d:
        assert localize.load_reconstruction(d) is None


# ---------------------------------------------------------------------------
# Stage 3 — 3D-weighted multipass clustering
# ---------------------------------------------------------------------------

def _unit(vec):
    v = np.asarray(vec, dtype=np.float32)
    return v / np.linalg.norm(v)


def _scene_3d():
    # Two objects A (~origin) and B (~14 m away), each seen in two images;
    # plus C with no 3D position. All look identical (cosine ≈ 1).
    images = {i: {"id": i, "path": f"img{i}", "width": 1000, "height": 1000}
              for i in (1, 2)}
    detections = [
        {"id": 101, "image_id": 1, "bbox": [0, 0, 10, 10], "class_name": "human"},  # A
        {"id": 102, "image_id": 2, "bbox": [0, 0, 10, 10], "class_name": "human"},  # A
        {"id": 103, "image_id": 1, "bbox": [0, 0, 10, 10], "class_name": "human"},  # B
        {"id": 104, "image_id": 2, "bbox": [0, 0, 10, 10], "class_name": "human"},  # B
        {"id": 105, "image_id": 1, "bbox": [0, 0, 10, 10], "class_name": "human"},  # C (no 3D)
    ]
    positions = {
        "101": {"xyz_local": [0.0, 0.0, 0.0]},
        "102": {"xyz_local": [0.5, 0.0, 0.0]},
        "103": {"xyz_local": [10.0, 10.0, 0.0]},
        "104": {"xyz_local": [10.5, 10.0, 0.0]},
        # 105 deliberately absent -> singleton
    }
    emb = {d["id"]: _unit([1.0, 0.0]) for d in detections}
    return detections, images, positions, emb


def _run_3d():
    detections, images, positions, emb = _scene_3d()
    embeddings.embed_detections = lambda *a, **k: emb  # bypass DINOv3
    clusters = r3d.run_reid_3d(detections, images, positions)
    return detections, clusters


def test_3d_objects_merge_near_split_far():
    detections, clusters = _run_3d()
    uid = {i: u for u, ids in clusters.items() for i in ids}
    assert uid[101] == uid[102]          # A's two views merge
    assert uid[103] == uid[104]          # B's two views merge
    assert uid[101] != uid[103]          # A and B stay separate (14 m apart)
    assert len(clusters[uid[105]]) == 1  # C has no 3D position -> singleton


def test_3d_no_same_image_clusters():
    detections, clusters = _run_3d()
    img_of = {d["id"]: d["image_id"] for d in detections}
    for det_ids in clusters.values():
        imgs = [img_of[i] for i in det_ids]
        assert len(imgs) == len(set(imgs)), f"same-image collision in {det_ids}"


def test_3d_total_coverage_and_contiguous_ids():
    detections, clusters = _run_3d()
    all_ids = sorted(d["id"] for d in detections)
    covered = sorted(i for ids in clusters.values() for i in ids)
    assert covered == all_ids
    assert len(covered) == len(set(covered))
    assert sorted(clusters.keys()) == list(range(1, len(clusters) + 1))


def test_3d_category_purity():
    detections, clusters = _run_3d()
    cat_of = {d["id"]: r3d.canonical_category(d["class_name"]) for d in detections}
    for det_ids in clusters.values():
        assert len({cat_of[i] for i in det_ids}) == 1


def test_canonical_category_mapping():
    assert r3d.canonical_category("Pedestrian") == "human"
    assert r3d.canonical_category("people") == "human"
    assert r3d.canonical_category("car") == "vehicle"
    assert r3d.canonical_category("Truck") == "vehicle"
    assert r3d.canonical_category("fire") == "fire"


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items())
           if k.startswith("test_") and callable(v)]
    failed = 0
    for fn in fns:
        try:
            fn()
            print(f"PASS {fn.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL {fn.__name__}: {e}")
    print(f"\n{len(fns) - failed}/{len(fns)} passed")
    sys.exit(1 if failed else 0)
