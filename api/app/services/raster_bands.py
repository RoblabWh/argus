"""Shared raster→GeoJSON helpers for map overlays.

Used by the fire overlay (services/fire_map.py) and the temperature overlay
(services/thermal_map.py): both rasterize data into a metric UTM grid, slice
it into value bands, and vectorize each band into GeoJSON polygon features.

Grid convention: row 0 = northern edge, `cell` metres per pixel,
(e_min, n_max) = UTM coordinate of the top-left grid corner.
"""
from functools import lru_cache

import cv2
import numpy as np
import pyproj

# Polygon simplification tolerance in raster cells.
SIMPLIFY_EPSILON_PX = 1.5


@lru_cache(maxsize=4)
def get_transformers(zone: int, north: bool):
    """(WGS84 -> UTM, UTM -> WGS84) transformer pair, both always_xy (lon/lat)."""
    epsg = f"EPSG:326{zone:02d}" if north else f"EPSG:327{zone:02d}"
    to_utm = pyproj.Transformer.from_crs("EPSG:4326", epsg, always_xy=True)
    to_wgs = pyproj.Transformer.from_crs(epsg, "EPSG:4326", always_xy=True)
    return to_utm, to_wgs


def smooth_mask(mask: np.ndarray, sigma_cells: float) -> np.ndarray:
    """Geometric (level-set) smoothing: blur the binary mask, re-threshold.

    The 0.5 threshold roughly preserves area, rounds corners, and bridges
    gaps smaller than ~sigma — the metaball-style merge. Blur is monotone
    w.r.t. mask inclusion, so smoothed value bands stay properly nested.
    """
    blurred = cv2.GaussianBlur(mask.astype(np.float32), (0, 0), sigma_cells)
    return (blurred >= 0.5).astype(np.uint8)


def grid_ring_to_lonlat(contour, e_min, n_max, cell, to_wgs):
    """Contour (Nx1x2 or Nx2 int px) -> closed GeoJSON ring [[lon, lat], ...]."""
    pts = contour.reshape(-1, 2).astype(np.float64)
    easting = e_min + (pts[:, 0] + 0.5) * cell
    northing = n_max - (pts[:, 1] + 0.5) * cell
    lon, lat = to_wgs.transform(easting, northing)
    ring = [[round(float(lo), 7), round(float(la), 7)] for lo, la in zip(lon, lat)]
    ring.append(ring[0])
    return ring


def trace_band_features(mask, labels, props, e_min, n_max, cell, to_wgs,
                        epsilon=SIMPLIFY_EPSILON_PX):
    """Vectorize one band mask into GeoJSON Polygon features (holes included).

    ``labels`` is a connected-component labeling of the overlay's base mask
    (the band mask must be a subset of it); every feature gets a ``region_id``
    property sampled from it, plus the caller's ``props``.
    """
    features = []
    contours, hierarchy = cv2.findContours(mask, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
    if hierarchy is None:
        return features
    hierarchy = hierarchy[0]  # [next, prev, first_child, parent]
    for idx, contour in enumerate(contours):
        if hierarchy[idx][3] != -1:
            continue  # holes are attached to their outer ring below
        # region_id from an original contour point — it lies inside the base
        # mask by construction, so its label is never 0.
        cy, cx = int(contour[0][0][1]), int(contour[0][0][0])
        region_id = int(labels[cy, cx])

        rings = []
        outer = cv2.approxPolyDP(contour, epsilon, True)
        if len(outer) < 3:
            continue
        rings.append(grid_ring_to_lonlat(outer, e_min, n_max, cell, to_wgs))
        child = hierarchy[idx][2]
        while child != -1:
            hole = cv2.approxPolyDP(contours[child], epsilon, True)
            if len(hole) >= 3:
                rings.append(grid_ring_to_lonlat(hole, e_min, n_max, cell, to_wgs))
            child = hierarchy[child][0]

        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "Polygon", "coordinates": rings},
                "properties": {"region_id": region_id, **props},
            }
        )
    return features
