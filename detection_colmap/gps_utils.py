"""EXIF/XMP GPS priors and GPS↔UTM conversion for COLMAP geo-registration.

COLMAP runs in a *local* metric frame: priors are written as ``UTM − geo_offset``
so all downstream coordinates (sparse points, camera centres, PLY) stay small
enough for float32. To recover true UTM: ``utm = local + geo_offset``.

Reference: ``colmap_reconstruction_and_localization_ARGUS.md`` §3.1.
"""
from __future__ import annotations

import logging
import math
import re

import pyproj
from PIL import Image
from PIL.ExifTags import GPSTAGS

logger = logging.getLogger(__name__)

# DJI flight altitude *above takeoff* lives in the XMP blob, not EXIF. Prefer it.
_XMP_REL_ALT_RE = re.compile(rb'RelativeAltitude="([+\-0-9\.]+)"')

# Cache transformers by target EPSG — building one per call is expensive and a
# flight shares a single UTM zone, so the cache stays tiny.
_TRANSFORMER_CACHE: dict[str, pyproj.Transformer] = {}


def _dms_to_deg(dms) -> float:
    d, m, s = (float(x) for x in dms)
    return d + m / 60.0 + s / 3600.0


def read_gps_alt(path: str):
    """Return ``(lat, lon, alt_metres)`` from EXIF/XMP, or ``None``.

    Prefers DJI relative altitude (XMP); falls back to absolute EXIF
    ``GPSAltitude``; finally ``0.0``. Without GPS the image cannot be
    geo-registered and is dropped from the priors.
    """
    try:
        img = Image.open(path)
    except Exception as e:  # noqa: BLE001 - unreadable image -> no prior
        logger.warning("[colmap] could not open %s for EXIF: %s", path, e)
        return None
    exif = img._getexif() or {}
    gps_raw = {GPSTAGS.get(k, k): v for k, v in (exif.get(34853) or {}).items()}
    lat_dms, lon_dms = gps_raw.get("GPSLatitude"), gps_raw.get("GPSLongitude")
    if not (lat_dms and lon_dms):
        return None
    lat = _dms_to_deg(lat_dms) * (-1 if gps_raw.get("GPSLatitudeRef") == "S" else 1)
    lon = _dms_to_deg(lon_dms) * (-1 if gps_raw.get("GPSLongitudeRef") == "W" else 1)

    alt = None
    xmp = img.info.get("xmp")
    if isinstance(xmp, (bytes, bytearray)):
        m = _XMP_REL_ALT_RE.search(bytes(xmp))
        if m:
            alt = float(m.group(1))
    if alt is None and gps_raw.get("GPSAltitude") is not None:
        alt = float(gps_raw["GPSAltitude"])  # absolute MSL fallback
    return lat, lon, (alt if alt is not None else 0.0)


def utm_epsg(lat: float, lon: float) -> str:
    zone = int((lon + 180) / 6) + 1
    return f"EPSG:326{zone:02d}" if lat >= 0 else f"EPSG:327{zone:02d}"


def gps_to_utm(lat: float, lon: float):
    """Project a WGS-84 (lat, lon) to UTM (easting, northing) in metres."""
    epsg = utm_epsg(lat, lon)
    transformer = _TRANSFORMER_CACHE.get(epsg)
    if transformer is None:
        transformer = pyproj.Transformer.from_crs("EPSG:4326", epsg, always_xy=False)
        _TRANSFORMER_CACHE[epsg] = transformer
    easting, northing = transformer.transform(lat, lon)
    return easting, northing


def build_priors(image_paths: dict[str, str]):
    """Build the local-frame priors from per-image EXIF GPS.

    Args:
        image_paths: ``{basename: absolute_path}`` for the reconstruction set.

    Returns:
        ``(priors_local, geo_offset, epsg)`` where ``priors_local`` is
        ``{basename: (e_local, n_local, alt_local)}`` (UTM − geo_offset),
        ``geo_offset`` is ``[e, n, 0]`` metres (floored to whole km), and
        ``epsg`` is the UTM zone string. Images without GPS are omitted.
    """
    priors_utm: dict[str, tuple] = {}
    epsg = None
    for name, path in image_paths.items():
        got = read_gps_alt(path)
        if got is None:
            continue
        lat, lon, alt = got
        e, n = gps_to_utm(lat, lon)
        epsg = epsg or utm_epsg(lat, lon)
        priors_utm[name] = (e, n, alt)

    if not priors_utm:
        return {}, [0.0, 0.0, 0.0], None

    # Floor the min easting/northing to whole km. Subtracting keeps every
    # downstream coordinate small (~thousands, not ~6-7 digit UTM) so float32
    # doesn't band. Floor-to-km keeps the offset stable across small changes to
    # the image set.
    geo_offset = [
        math.floor(min(e for e, _, _ in priors_utm.values()) / 1000.0) * 1000.0,
        math.floor(min(n for _, n, _ in priors_utm.values()) / 1000.0) * 1000.0,
        0.0,
    ]
    priors_local = {
        name: (e - geo_offset[0], n - geo_offset[1], alt - geo_offset[2])
        for name, (e, n, alt) in priors_utm.items()
    }
    return priors_local, geo_offset, epsg
