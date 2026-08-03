"""Ground-position estimation for the spatial gate (reusable).

Each detection's bbox centroid is interpolated to a GPS coordinate from the 4
image corners, then projected to UTM so distances can be compared in metres.

This is the swappable "distance" component: a future approach could replace it
with a 3D-pointcloud-derived position while keeping the rest of the pipeline.
"""
from __future__ import annotations

import pyproj

# Cache transformers by target EPSG — building one per call is expensive and a
# flight shares a single UTM zone, so the cache stays tiny.
_TRANSFORMER_CACHE: dict[str, pyproj.Transformer] = {}


def interpolate_detection_gps(bbox, image_width, image_height, corners_gps, src_px=None):
    """Bilinearly interpolate the bbox-centre GPS position from image corners.

    Args:
        bbox: [x, y, w, h] in absolute pixels (top-left origin).
        corners_gps: 4 corners [TL, TR, BR, BL], each [lat, lon] (WGS-84).
        src_px: ``[x0, y0, x1, y1]`` — the image region those corners were
            computed from. Defaults to the full frame. The mapping pipeline
            falls back to the image's *lower half* for footprints that would
            otherwise be implausibly large, and normalizing such corners against
            the full height would place every detection wrongly.

    Returns:
        [lat, lon] of the bbox centre.
    """
    x0, y0, x1, y1 = src_px if src_px else (0.0, 0.0, image_width, image_height)
    span_x = (x1 - x0) or 1.0
    span_y = (y1 - y0) or 1.0
    cx = (bbox[0] + bbox[2] / 2 - x0) / span_x  # normalized [0,1] horizontal
    cy = (bbox[1] + bbox[3] / 2 - y0) / span_y  # normalized [0,1] vertical
    tl, tr, br, bl = corners_gps
    top_lat = tl[0] + cx * (tr[0] - tl[0])
    top_lon = tl[1] + cx * (tr[1] - tl[1])
    bot_lat = bl[0] + cx * (br[0] - bl[0])
    bot_lon = bl[1] + cx * (br[1] - bl[1])
    lat = top_lat + cy * (bot_lat - top_lat)
    lon = top_lon + cy * (bot_lon - top_lon)
    return [lat, lon]


def _utm_epsg(lat, lon):
    zone = int((lon + 180) / 6) + 1
    return f"EPSG:326{zone:02d}" if lat >= 0 else f"EPSG:327{zone:02d}"


def gps_to_utm(lat, lon, epsg=None):
    """Project a WGS-84 (lat, lon) to UTM (easting, northing) in metres.

    ``epsg`` pins the target zone — pass the reconstruction's own ``utm_epsg``
    so positions stay comparable across a flight that straddles a zone boundary.
    Defaults to the zone the point itself falls in.
    """
    epsg = epsg or _utm_epsg(lat, lon)
    transformer = _TRANSFORMER_CACHE.get(epsg)
    if transformer is None:
        transformer = pyproj.Transformer.from_crs("EPSG:4326", epsg, always_xy=False)
        _TRANSFORMER_CACHE[epsg] = transformer
    easting, northing = transformer.transform(lat, lon)
    return easting, northing
