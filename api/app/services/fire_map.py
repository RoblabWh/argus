"""Vector fire map built from fire-class detections.

Turns the per-image fire detections into a smooth, georeferenced confidence
field and vectorizes it into GeoJSON polygon bands for the frontend's Leaflet
overlay:

1. Each detection bbox is projected to GPS by bilinear interpolation from its
   image's 4 map-element corners (same math as the reID worker and the
   frontend's computeDetectionGps), then to UTM so the raster grid is metric.
2. All bbox quads are rasterized into one confidence field with per-pixel
   *max* — heavily overlapping detections keep the strongest confidence
   instead of fragmenting into islands.
3. The field is sliced into confidence bands (height-map style). Each band
   mask is smoothed geometrically (Gaussian blur + 0.5 threshold): hard box
   corners become rounded blobs and nearby boxes melt together, while the
   confidence values themselves stay untouched (a weak isolated detection
   can never be blurred out of existence).
4. Each smoothed band is vectorized via contour tracing into GeoJSON
   polygons (holes included).
5. Connected regions are labeled so every polygon carries a region_id, and a
   region table maps back to the source images/detections for interactivity.

Everywhere without detections stays uncovered (transparent on the map).
"""
import logging

import cv2
import numpy as np

from app.services.raster_bands import get_transformers, smooth_mask, trace_band_features

logger = logging.getLogger(__name__)

# Ultralytics' default confidence floor — no detection scores below this, so
# it is the outer edge of the lowest band.
BASE_CONFIDENCE = 0.25
NUM_BANDS = 7
# Gaussian sigma in metres: how far the box corners melt into blobs. Capped
# relative to the smallest detection so tiny fires aren't smoothed away.
SMOOTH_RADIUS_M = 1.5
# Raster sizing: metre-per-cell floor and overall grid cap.
MIN_CELL_M = 0.05
MAX_GRID_DIM = 1536

EMPTY_RESULT = {"geojson": None, "regions": {}}


def _interpolate_px_to_gps(px: float, py: float, width: int, height: int, corners_gps,
                           src_px=None):
    """Bilinearly interpolate an image pixel to GPS from the 4 image corners.

    corners_gps: [TL, TR, BR, BL], each [lat, lon] (the MapElement convention,
    same as reid/spatial.py in the YOLO worker).
    src_px: [x0, y0, x1, y1] — the image region those corners were traced from.
    Defaults to the full frame; the mapping pipeline uses the lower half for
    steeply tilted footprints, and normalizing those against the full height
    would misplace every pixel.
    """
    x0, y0, x1, y1 = src_px if src_px else (0.0, 0.0, width, height)
    rx = (px - x0) / ((x1 - x0) or 1.0)
    ry = (py - y0) / ((y1 - y0) or 1.0)
    tl, tr, br, bl = corners_gps
    top_lat = tl[0] + rx * (tr[0] - tl[0])
    top_lon = tl[1] + rx * (tr[1] - tl[1])
    bot_lat = bl[0] + rx * (br[0] - bl[0])
    bot_lon = bl[1] + rx * (br[1] - bl[1])
    return top_lat + ry * (bot_lat - top_lat), top_lon + ry * (bot_lon - top_lon)


def _project_detection_quads(detections: list[dict], images_by_id: dict):
    """Project each detection bbox to a UTM quad.

    Returns (quads, transformer_to_wgs) where quads is a list of
    {"utm": 4x2 float array, "score", "detection_id", "image_id"}.
    Detections on images without georeferencing are skipped.
    """
    to_utm = to_wgs = None
    quads = []
    for det in detections:
        img = images_by_id.get(det["image_id"])
        if not img or not img.get("corners_gps") or not img.get("width") or not img.get("height"):
            continue
        x, y, w, h = det["bbox"]
        corner_px = ((x, y), (x + w, y), (x + w, y + h), (x, y + h))
        gps = [
            _interpolate_px_to_gps(cx, cy, img["width"], img["height"],
                                   img["corners_gps"], img.get("corners_src_px"))
            for cx, cy in corner_px
        ]
        if to_utm is None:
            lat0, lon0 = gps[0]
            zone = int((lon0 + 180) / 6) + 1
            to_utm, to_wgs = get_transformers(zone, lat0 >= 0)
        utm = np.array([to_utm.transform(lon, lat) for lat, lon in gps], dtype=np.float64)
        quads.append(
            {
                "utm": utm,
                "score": float(det.get("score") or 0.0),
                "detection_id": det["id"],
                "image_id": det["image_id"],
            }
        )
    return quads, to_wgs


def _make_grid(quads: list[dict]):
    """Metric raster grid covering all quads plus a smoothing margin."""
    all_pts = np.vstack([q["utm"] for q in quads])
    margin = 3 * SMOOTH_RADIUS_M
    e_min, n_min = all_pts.min(axis=0) - margin
    e_max, n_max = all_pts.max(axis=0) + margin
    extent = max(e_max - e_min, n_max - n_min, 1e-6)
    cell = max(MIN_CELL_M, extent / MAX_GRID_DIM)
    grid_w = max(int(np.ceil((e_max - e_min) / cell)), 2)
    grid_h = max(int(np.ceil((n_max - n_min) / cell)), 2)
    return e_min, n_max, cell, grid_w, grid_h


def _quad_to_grid_px(quad_utm, e_min, n_max, cell):
    """UTM quad -> int32 pixel polygon (row 0 = northern edge)."""
    cols = (quad_utm[:, 0] - e_min) / cell
    rows = (n_max - quad_utm[:, 1]) / cell
    return np.stack([cols, rows], axis=1).round().astype(np.int32)


def _assign_regions(quads, labels, grid_w, grid_h, e_min, n_max, cell, images_by_id):
    """Map each connected fire region to the detections/images that formed it."""
    regions: dict[int, dict] = {}
    tmp = np.zeros((grid_h, grid_w), dtype=np.uint8)
    for quad in quads:
        tmp.fill(0)
        cv2.fillPoly(tmp, [_quad_to_grid_px(quad["utm"], e_min, n_max, cell)], 1)
        quad_labels = labels[tmp > 0]
        quad_labels = quad_labels[quad_labels > 0]
        if quad_labels.size == 0:
            continue  # blurred below the base confidence — not part of any region
        region_id = int(np.bincount(quad_labels).argmax())
        region = regions.setdefault(
            region_id, {"max_score": 0.0, "detection_count": 0, "_image_ids": set()}
        )
        region["max_score"] = max(region["max_score"], quad["score"])
        region["detection_count"] += 1
        region["_image_ids"].add(quad["image_id"])

    out = {}
    for region_id, region in regions.items():
        images = []
        for image_id in sorted(region["_image_ids"]):
            img = images_by_id.get(image_id, {})
            images.append(
                {
                    "image_id": image_id,
                    "filename": img.get("filename"),
                    "thumbnail_url": img.get("thumbnail_url"),
                }
            )
        out[str(region_id)] = {
            "max_score": round(region["max_score"], 3),
            "detection_count": region["detection_count"],
            "images": images,
        }
    return out


def _vectorize_bands(field, labels, sigma_cells, e_min, n_max, cell, to_wgs, floor):
    """Slice the confidence field into bands and trace them into features."""
    field_max = float(field.max())
    span = max(field_max - floor, 1e-6)
    thresholds = [floor + i * span / NUM_BANDS for i in range(NUM_BANDS)]

    features = []
    for level, threshold in enumerate(thresholds):
        mask = smooth_mask(field >= threshold, sigma_cells)
        if not mask.any():
            break
        features.extend(
            trace_band_features(
                mask, labels,
                {"level": level, "conf_min": round(threshold, 3)},
                e_min, n_max, cell, to_wgs,
            )
        )
    return features


def build_fire_map(fire_input: dict, min_confidence: float | None = None) -> dict:
    """Build the fire overlay from a get_fire_map_input payload.

    Returns {"geojson": FeatureCollection | None, "regions": {...}} — see the
    module docstring. Features are ordered low band -> high band so painting
    them in order produces the height-map look.

    min_confidence raises the confidence floor above BASE_CONFIDENCE:
    detections below it are dropped entirely (they must not influence grid
    sizing, the smoothing cap, or region attribution) and it becomes the
    outer edge of the lowest band.
    """
    floor = max(min_confidence or 0.0, BASE_CONFIDENCE)
    detections = [
        det for det in fire_input.get("detections", [])
        if float(det.get("score") or 0.0) >= floor
    ]
    images_by_id = {img["id"]: img for img in fire_input.get("images", [])}
    quads, to_wgs = _project_detection_quads(detections, images_by_id)
    if not quads:
        return dict(EMPTY_RESULT)

    e_min, n_max, cell, grid_w, grid_h = _make_grid(quads)
    field = np.zeros((grid_h, grid_w), dtype=np.float32)
    tmp = np.zeros((grid_h, grid_w), dtype=np.uint8)
    for quad in quads:
        tmp.fill(0)
        cv2.fillPoly(tmp, [_quad_to_grid_px(quad["utm"], e_min, n_max, cell)], 1)
        np.maximum(field, tmp.astype(np.float32) * quad["score"], out=field)

    # Cap the smoothing radius by the smallest detection so no blob is
    # smoothed below the 0.5 re-threshold and disappears.
    min_side = min(
        float(np.linalg.norm(q["utm"][i] - q["utm"][(i + 1) % 4]))
        for q in quads
        for i in range(4)
    )
    sigma_cells = max(min(SMOOTH_RADIUS_M, 0.6 * min_side) / cell, 1.0)

    base_mask = smooth_mask(field >= floor, sigma_cells)
    if not base_mask.any():
        return dict(EMPTY_RESULT)
    _, labels = cv2.connectedComponents(base_mask)

    regions = _assign_regions(quads, labels, grid_w, grid_h, e_min, n_max, cell, images_by_id)
    features = _vectorize_bands(field, labels, sigma_cells, e_min, n_max, cell, to_wgs, floor)

    logger.info(
        "Fire map: %d detections -> %d regions, %d band polygons (grid %dx%d, %.2f m/cell)",
        len(quads), len(regions), len(features), grid_w, grid_h, cell,
    )
    return {
        "geojson": {"type": "FeatureCollection", "features": features},
        "regions": regions,
    }
