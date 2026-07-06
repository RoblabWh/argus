"""Verification of the reID clustering against the guide's §11 checklist.

Runs without torch/transformers/pyproj installed: pyproj is stubbed with a
simple local equirectangular projection and the DINOv3 embedding step is
monkeypatched with crafted unit vectors, so we exercise the gating + union-find
logic deterministically.

Run:  python -m pytest detection_yolo/tests/test_reid.py
  or:  python detection_yolo/tests/test_reid.py
"""
import math
import sys
import types
from pathlib import Path

import numpy as np

# --- make `reid` importable and stub pyproj before importing the package ---
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
            # crude local metres: 1 deg lat ~ 111320 m, lon scaled by cos(lat)
            e = lon * 111320.0 * math.cos(math.radians(lat))
            n = lat * 111320.0
            return e, n

    pyproj.Transformer = _T
    sys.modules["pyproj"] = pyproj


_install_pyproj_stub()

from reid import by_dinov3, embeddings  # noqa: E402
from reid.clustering import UnionFind, constrained_merge  # noqa: E402
from reid.spatial import interpolate_detection_gps  # noqa: E402


def _unit(vec):
    v = np.asarray(vec, dtype=np.float32)
    return v / np.linalg.norm(v)


# A small synthetic scene. Two real objects (A, B) ~50 m apart, each seen in
# two overlapping images, plus a lone object C. Same-uniform appearance means
# A and B embeddings are similar — only the spatial gate keeps them apart.
# corners_gps are [TL, TR, BR, BL] over a ~ (lat 50.00..50.001, lon 7.00..7.001) tile.
def _scene():
    corners = [[50.0010, 7.0000], [50.0010, 7.0010], [50.0000, 7.0010], [50.0000, 7.0000]]
    images = {
        1: {"id": 1, "path": "img1", "width": 1000, "height": 1000, "corners_gps": corners},
        2: {"id": 2, "path": "img2", "width": 1000, "height": 1000, "corners_gps": corners},
        3: {"id": 3, "path": "img3", "width": 1000, "height": 1000, "corners_gps": None},  # no georef
    }
    # bbox centres: A near top-left (~0,0 -> lat 50.001/lon 7.000),
    #               B near bottom-right (~lat 50.000/lon 7.001) ~ >100 m away.
    detections = [
        {"id": 101, "image_id": 1, "bbox": [10, 10, 20, 20], "class_name": "human"},   # A in img1
        {"id": 102, "image_id": 2, "bbox": [14, 12, 20, 20], "class_name": "human"},   # A in img2
        {"id": 103, "image_id": 1, "bbox": [960, 960, 20, 20], "class_name": "human"}, # B in img1
        {"id": 104, "image_id": 2, "bbox": [958, 962, 20, 20], "class_name": "human"}, # B in img2
        {"id": 105, "image_id": 3, "bbox": [500, 500, 20, 20], "class_name": "human"}, # C, no georef
    ]
    # All humans look near-identical (same uniform): high cosine sim everywhere.
    emb = {d["id"]: _unit([1.0, 0.02 * i]) for i, d in enumerate(detections)}
    return detections, images, emb


def _run():
    detections, images, emb = _scene()
    embeddings.embed_detections = lambda *a, **k: emb  # bypass DINOv3
    # Neighbor radius is per-category now (NEIGHBOR_RADIUS_BY_CATEGORY_M);
    # "human" uses the default 8 m, which fits this scene's geometry.
    clusters = by_dinov3.run_reid(detections, images, sim_threshold=0.65)
    return detections, clusters


def test_no_same_image_clusters():
    detections, clusters = _run()
    img_of = {d["id"]: d["image_id"] for d in detections}
    for det_ids in clusters.values():
        imgs = [img_of[i] for i in det_ids]
        assert len(imgs) == len(set(imgs)), f"same-image collision in {det_ids}"


def test_total_coverage():
    detections, clusters = _run()
    all_ids = sorted(d["id"] for d in detections)
    covered = sorted(i for ids in clusters.values() for i in ids)
    assert covered == all_ids
    assert len(covered) == len(set(covered)), "a detection appears in two clusters"


def test_contiguous_ids():
    _, clusters = _run()
    assert sorted(clusters.keys()) == list(range(1, len(clusters) + 1))


def test_objects_merge_within_radius_and_split_across():
    detections, clusters = _run()
    uid_of = {i: uid for uid, ids in clusters.items() for i in ids}
    # A's two views merge; B's two views merge; A and B stay separate.
    assert uid_of[101] == uid_of[102]
    assert uid_of[103] == uid_of[104]
    assert uid_of[101] != uid_of[103]
    # C has no georef -> its own singleton.
    assert len(clusters[uid_of[105]]) == 1


def test_determinism():
    _, c1 = _run()
    _, c2 = _run()
    norm = lambda c: sorted(tuple(sorted(v)) for v in c.values())
    assert norm(c1) == norm(c2)


def test_interpolation_matches_frontend_formula():
    # Corners are stored [TL, TR, BR, BL] each [lat, lon] (see coordinateUtils.ts).
    # Replicate the frontend's computeDetectionGps and assert equality.
    tl, tr, br, bl = [51.0010, 7.0000], [51.0010, 7.0010], [51.0000, 7.0010], [51.0000, 7.0000]
    corners = [tl, tr, br, bl]
    w, h = 4000, 3000
    bbox = [879.0, 2289.0, 166.0, 288.0]
    rel_x = (bbox[0] + bbox[2] / 2) / w
    rel_y = (bbox[1] + bbox[3] / 2) / h
    # frontend: c0=corners[1] (TR), c1=corners[2] (BR), c2=corners[3] (BL), c3=corners[0] (TL)
    c0, c1, c2, c3 = corners[1], corners[2], corners[3], corners[0]
    top = [c3[0] * (1 - rel_x) + c0[0] * rel_x, c3[1] * (1 - rel_x) + c0[1] * rel_x]
    bot = [c2[0] * (1 - rel_x) + c1[0] * rel_x, c2[1] * (1 - rel_x) + c1[1] * rel_x]
    fe_lat = top[0] * (1 - rel_y) + bot[0] * rel_y
    fe_lon = top[1] * (1 - rel_y) + bot[1] * rel_y

    lat, lon = interpolate_detection_gps(bbox, w, h, corners)
    assert abs(lat - fe_lat) < 1e-12, (lat, fe_lat)
    assert abs(lon - fe_lon) < 1e-12, (lon, fe_lon)


def test_unionfind_basic():
    uf = UnionFind(3)
    uf.union(0, 1)
    assert uf.find(0) == uf.find(1)
    assert uf.find(0) != uf.find(2)


def test_constrained_merge_rejects_same_image():
    # nodes 0,1 same image -> never merge despite strongest edge
    roots = constrained_merge([(0, 1, 0.99)], image_ids=[7, 7], n=2)
    assert roots[0] != roots[1]


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
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
