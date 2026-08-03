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
    """Return ``(lat, lon, rel_alt, abs_alt)`` from EXIF/XMP, or ``None``.

    ``rel_alt`` is DJI's height above takeoff (XMP) and ``abs_alt`` is EXIF
    ``GPSAltitude`` (MSL); either may be ``None``. The two are *different
    datums* — the caller picks one for the whole image set, because mixing them
    within a flight corrupts the vertical geo-registration. Without GPS the
    image cannot be geo-registered and is dropped from the priors.
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

    rel_alt = None
    xmp = img.info.get("xmp")
    if isinstance(xmp, (bytes, bytearray)):
        m = _XMP_REL_ALT_RE.search(bytes(xmp))
        if m:
            rel_alt = float(m.group(1))
    abs_alt = None
    if gps_raw.get("GPSAltitude") is not None:
        abs_alt = float(gps_raw["GPSAltitude"])
    return lat, lon, rel_alt, abs_alt


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
        ``geo_offset`` is ``[e, n, 0]`` metres (E/N floored to whole km), and
        ``epsg`` is the UTM zone string. Images without GPS are omitted.

    A single altitude datum is chosen for the whole set: DJI's relative height
    above takeoff when *every* image carries it, otherwise absolute EXIF MSL for
    every image. Mixing the two within one flight would feed metres-to-hundreds
    of metres of vertical inconsistency straight into ``model_aligner``.

    Which datum won is *not* encoded in ``geo_offset`` — the camera altitudes
    say nothing about where the terrain is. Consumers that need a ground plane
    measure it from the reconstructed point cloud instead of assuming z = 0.
    """
    raw: dict[str, tuple] = {}  # name -> (e, n, rel_alt|None, abs_alt|None)
    epsg = None
    for name, path in image_paths.items():
        got = read_gps_alt(path)
        if got is None:
            continue
        lat, lon, rel_alt, abs_alt = got
        e, n = gps_to_utm(lat, lon)
        epsg = epsg or utm_epsg(lat, lon)
        raw[name] = (e, n, rel_alt, abs_alt)

    if not raw:
        return {}, [0.0, 0.0, 0.0], None

    use_relative = all(rel is not None for _, _, rel, _ in raw.values())
    if use_relative:
        alts = {name: rel for name, (_, _, rel, _) in raw.items()}
    else:
        missing_abs = [name for name, (_, _, _, ab) in raw.items() if ab is None]
        if missing_abs:
            logger.warning(
                "[colmap] %d/%d images have neither XMP RelativeAltitude nor EXIF "
                "GPSAltitude — using 0.0 for them, vertical alignment will suffer",
                len(missing_abs), len(raw),
            )
        alts = {name: (ab if ab is not None else 0.0) for name, (_, _, _, ab) in raw.items()}
        logger.info(
            "[colmap] not every image carries XMP RelativeAltitude — using absolute "
            "EXIF altitude for the whole set"
        )

    # Floor the min easting/northing to whole km. Subtracting keeps every
    # downstream coordinate small (~thousands, not ~6-7 digit UTM) so float32
    # doesn't band. Floor-to-km keeps the offset stable across small changes to
    # the image set. Altitudes are left in their chosen datum (z offset 0).
    geo_offset = [
        math.floor(min(e for e, _, _, _ in raw.values()) / 1000.0) * 1000.0,
        math.floor(min(n for _, n, _, _ in raw.values()) / 1000.0) * 1000.0,
        0.0,
    ]
    priors_local = {
        name: (e - geo_offset[0], n - geo_offset[1], alts[name] - geo_offset[2])
        for name, (e, n, _, _) in raw.items()
    }
    return priors_local, geo_offset, epsg
