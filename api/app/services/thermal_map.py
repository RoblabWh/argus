"""Interactive temperature overlay built from radiometric thermal images.

Merges a report's per-image float32 temperature matrices
(``reports_data/{id}/thermal/{image_id}.npy``) into one georeferenced
temperature field per IR map — **per-pixel max** where IR images overlap —
then slices it into fixed temperature bands (default 10 °C), optionally
clipped to a min/max range, and vectorizes the bands into GeoJSON for the
frontend's Leaflet overlay (same pattern as services/fire_map.py).

The compositing (loading + warping every matrix) is the expensive part, so
the composite is cached as ``reports_data/{id}/temp_composite_{map_id}.npz``.
Re-processing a report creates new Map rows (new ids) and report deletion
wipes the folder, so stale caches are never served. Banding a cached
composite takes tens of milliseconds — cheap enough that the overlay can
live-update as the user changes the gallery's temperature filters.

Thermal images without raw temperature data (color-mapped only, no ``.npy``)
are skipped entirely — they are not thermally analyzable.
"""
import logging
import math
import os

import cv2
import numpy as np

from app.config import config
from app.services.raster_bands import get_transformers, smooth_mask, trace_band_features

logger = logging.getLogger(__name__)

# Band step in °C.
DEFAULT_STEP = 10.0
# Raster sizing: metre-per-cell floor and overall grid cap.
MIN_CELL_M = 0.05
MAX_GRID_DIM = 2048
# Geometric smoothing of band outlines (warped 640x512 matrices look blocky).
SMOOTH_SIGMA_CELLS = 1.0
# Sentinel for grid pixels not covered by any thermal image.
NO_DATA = -1.0e9

EMPTY_RESULT = {"geojson": None, "regions": {}, "range": None}


def _composite_cache_path(report_id: int, map_id: int) -> str:
    return str(config.UPLOAD_DIR / str(report_id) / f"temp_composite_{map_id}.npz")


def _grid_from_bounds(bounds_utm: dict):
    """Metric raster grid covering the map's UTM extent."""
    e_min = float(bounds_utm["easting_min"])
    e_max = float(bounds_utm["easting_max"])
    n_min = float(bounds_utm["northing_min"])
    n_max = float(bounds_utm["northing_max"])
    extent = max(e_max - e_min, n_max - n_min, 1e-6)
    cell = max(MIN_CELL_M, extent / MAX_GRID_DIM)
    grid_w = max(int(math.ceil((e_max - e_min) / cell)), 2)
    grid_h = max(int(math.ceil((n_max - n_min) / cell)), 2)
    return e_min, n_max, cell, grid_w, grid_h


def _utm_quad_to_grid_px(corners_utm, e_min, n_max, cell) -> np.ndarray:
    """4 UTM corners [TL, TR, BR, BL] -> float32 grid pixel quad."""
    pts = np.asarray(corners_utm, dtype=np.float64)
    cols = (pts[:, 0] - e_min) / cell
    rows = (n_max - pts[:, 1]) / cell
    return np.stack([cols, rows], axis=1).astype(np.float32)


def _build_composite(elements: list[dict], e_min, n_max, cell, grid_w, grid_h):
    """Warp every analyzable element's temperature matrix into the grid (max)."""
    temp = np.full((grid_h, grid_w), NO_DATA, dtype=np.float32)
    valid = np.zeros((grid_h, grid_w), dtype=np.uint8)

    for el in elements:
        try:
            matrix = np.load(el["temp_matrix_path"]).astype(np.float32)
        except Exception as e:  # noqa: BLE001 - one broken matrix must not kill the map
            logger.warning("Skipping thermal matrix %s: %s", el["temp_matrix_path"], e)
            continue
        h, w = matrix.shape[:2]
        # Image corners [TL, TR, BR, BL] map onto the element's UTM corners
        # (same correspondence the detection GPS interpolation relies on).
        src = np.array([[0, 0], [w, 0], [w, h], [0, h]], dtype=np.float32)
        dst = _utm_quad_to_grid_px(el["corners_utm"], e_min, n_max, cell)
        transform = cv2.getPerspectiveTransform(src, dst)
        # BORDER_REPLICATE keeps bilinear taps at the matrix edge from mixing
        # with an out-of-image constant; the nearest-warped mask below is the
        # sole authority on which grid pixels are actually covered.
        warped = cv2.warpPerspective(
            matrix, transform, (grid_w, grid_h),
            flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE,
        )
        mask = cv2.warpPerspective(
            np.ones((h, w), dtype=np.float32), transform, (grid_w, grid_h),
            flags=cv2.INTER_NEAREST, borderMode=cv2.BORDER_CONSTANT, borderValue=0,
        )
        covered = mask > 0.5
        np.maximum(temp, np.where(covered, warped, NO_DATA), out=temp)
        valid[covered] = 1

    return temp, valid


def _get_or_build_composite(report_id: int, ir_map: dict):
    """Load the cached composite for one IR map, building it on first use.

    Returns (temp, valid, e_min, n_max, cell, zone, north) or None when the
    map has no analyzable thermal elements.
    """
    elements = [el for el in ir_map["elements"] if el.get("temp_matrix_path")]
    elements = [el for el in elements if os.path.isfile(el["temp_matrix_path"])]
    if not elements:
        return None

    bounds_utm = ir_map["bounds_utm"]
    zone = int(bounds_utm["zone"])
    north = str(bounds_utm.get("hemisphere", "N")).upper().startswith("N")

    cache_path = _composite_cache_path(report_id, ir_map["id"])
    if os.path.isfile(cache_path):
        try:
            cached = np.load(cache_path)
            return (
                cached["temp"], cached["valid"],
                float(cached["e_min"]), float(cached["n_max"]), float(cached["cell"]),
                zone, north,
            )
        except Exception as e:  # noqa: BLE001 - corrupt cache -> rebuild
            logger.warning("Rebuilding corrupt thermal composite %s: %s", cache_path, e)

    e_min, n_max, cell, grid_w, grid_h = _grid_from_bounds(bounds_utm)
    temp, valid = _build_composite(elements, e_min, n_max, cell, grid_w, grid_h)
    if not valid.any():
        return None
    try:
        np.savez_compressed(
            cache_path, temp=temp, valid=valid, e_min=e_min, n_max=n_max, cell=cell
        )
    except Exception as e:  # noqa: BLE001 - cache write is an optimization only
        logger.warning("Could not cache thermal composite %s: %s", cache_path, e)
    logger.info(
        "Built thermal composite for map %s (%d matrices, grid %dx%d, %.2f m/cell)",
        ir_map["id"], len(elements), grid_w, grid_h, cell,
    )
    return temp, valid, e_min, n_max, cell, zone, north


def _assign_regions(ir_map, labels, label_offset, e_min, n_max, cell, temp, base_mask):
    """Map each connected region to the thermal images covering it + its max temp."""
    regions: dict[str, dict] = {}
    grid_h, grid_w = labels.shape
    tmp = np.zeros((grid_h, grid_w), dtype=np.uint8)

    n_labels = int(labels.max())
    for label in range(1, n_labels + 1):
        region_mask = labels == label
        regions[str(label + label_offset)] = {
            "max_temp": round(float(temp[region_mask].max()), 1),
            "images": [],
            "_seen": set(),
        }

    for el in ir_map["elements"]:
        if not el.get("temp_matrix_path"):
            continue
        tmp.fill(0)
        quad = _utm_quad_to_grid_px(el["corners_utm"], e_min, n_max, cell)
        cv2.fillPoly(tmp, [quad.round().astype(np.int32)], 1)
        el_labels = labels[(tmp > 0) & (base_mask > 0)]
        el_labels = np.unique(el_labels[el_labels > 0])
        for label in el_labels:
            region = regions[str(int(label) + label_offset)]
            if el["image_id"] in region["_seen"]:
                continue
            region["_seen"].add(el["image_id"])
            region["images"].append(
                {
                    "image_id": el["image_id"],
                    "filename": el.get("filename"),
                    "thumbnail_url": el.get("thumbnail_url"),
                }
            )

    for region in regions.values():
        region.pop("_seen")
        region["images"].sort(key=lambda img: img["image_id"])
    return regions


def build_thermal_map(tm_input: dict, t_min: float | None = None,
                      t_max: float | None = None, step: float = DEFAULT_STEP) -> dict:
    """Build the temperature overlay from a get_thermal_map_input payload.

    Returns {"geojson": FeatureCollection | None, "regions": {...},
    "range": {"min", "max"} | None}. ``range`` is the unclipped data range so
    the UI can hint sensible filter values. Features are ordered low band ->
    high band per map (paint order = height-map look).
    """
    report_id = tm_input["report_id"]
    features: list = []
    regions: dict = {}
    grand_min: float | None = None
    grand_max: float | None = None
    label_offset = 0

    for ir_map in tm_input.get("maps", []):
        composite = _get_or_build_composite(report_id, ir_map)
        if composite is None:
            continue
        temp, valid, e_min, n_max, cell, zone, north = composite
        valid_bool = valid.astype(bool)

        data_min = float(temp[valid_bool].min())
        data_max = float(temp[valid_bool].max())
        grand_min = data_min if grand_min is None else min(grand_min, data_min)
        grand_max = data_max if grand_max is None else max(grand_max, data_max)

        lo = data_min if t_min is None else max(float(t_min), data_min)
        hi = data_max if t_max is None else min(float(t_max), data_max)
        if lo > hi:
            continue

        clip = (valid_bool & (temp >= lo) & (temp <= hi)).astype(np.uint8)
        if not clip.any():
            continue

        # Smoothing is unioned with the raw mask so tiny hotspots (single hot
        # pixels — embers) can never be smoothed out of the safety overlay.
        def banded(mask: np.ndarray) -> np.ndarray:
            return smooth_mask(mask, SMOOTH_SIGMA_CELLS) | mask

        base_mask = banded(clip)
        _, labels = cv2.connectedComponents(base_mask)

        _, to_wgs = get_transformers(zone, north)
        first_level = math.floor(lo / step) * step
        level = first_level
        while level <= hi:
            mask = banded(clip & (temp >= level))
            if not mask.any():
                break
            for feature in trace_band_features(
                mask, labels,
                {"temp_min": round(max(level, lo), 1), "temp_max": round(level + step, 1)},
                e_min, n_max, cell, to_wgs,
            ):
                feature["properties"]["region_id"] += label_offset
                features.append(feature)
            level += step

        regions.update(
            _assign_regions(ir_map, labels, label_offset, e_min, n_max, cell, temp, base_mask)
        )
        label_offset += int(labels.max())

    if not features:
        result = dict(EMPTY_RESULT)
        if grand_min is not None:
            # Data exists but the clip range excluded everything.
            result["range"] = {"min": round(grand_min, 1), "max": round(grand_max, 1)}
        return result

    # Drop regions that ended up without any band polygon (fully smoothed away).
    used_ids = {str(f["properties"]["region_id"]) for f in features}
    regions = {rid: region for rid, region in regions.items() if rid in used_ids}

    logger.info(
        "Thermal map for report %s: %d band polygons, %d regions (clip %s..%s)",
        report_id, len(features), len(regions), t_min, t_max,
    )
    return {
        "geojson": {"type": "FeatureCollection", "features": features},
        "regions": regions,
        "range": {"min": round(grand_min, 1), "max": round(grand_max, 1)},
    }
