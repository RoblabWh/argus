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


def interpolate_detection_gps(bbox, image_width, image_height, corners_gps):
    """Bilinearly interpolate the bbox-centre GPS position from image corners.

    Args:
        bbox: [x, y, w, h] in absolute pixels (top-left origin).
        corners_gps: 4 corners [TL, TR, BR, BL], each [lat, lon] (WGS-84).

    Returns:
        [lat, lon] of the bbox centre.
    """
    cx = (bbox[0] + bbox[2] / 2) / image_width  # normalized [0,1] horizontal
    cy = (bbox[1] + bbox[3] / 2) / image_height  # normalized [0,1] vertical
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


def gps_to_utm(lat, lon):
    """Project a WGS-84 (lat, lon) to UTM (easting, northing) in metres."""
    epsg = _utm_epsg(lat, lon)
    transformer = _TRANSFORMER_CACHE.get(epsg)
    if transformer is None:
        transformer = pyproj.Transformer.from_crs("EPSG:4326", epsg, always_xy=False)
        _TRANSFORMER_CACHE[epsg] = transformer
    easting, northing = transformer.transform(lat, lon)
    return easting, northing
