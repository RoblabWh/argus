"""Map file export for user downloads.

Turns a stored map (PNG on disk + `bounds` JSONB) into the format the user asked
for: the raw PNG, a WGS84 GeoTIFF, or a GeoTIFF in the map's native UTM zone.

This intentionally duplicates the rasterio logic of
`drz_backend_sharing.create_geo_tiff` instead of reusing it — the DRZ upload path
must stay byte-identical, and it writes to `map.url.replace('png', 'tif')`, which
for ODM maps is WebODM's own orthophoto. Outputs here use distinct suffixes so
nothing is overwritten.
"""

import logging
import os
import threading
from pathlib import Path

import cv2
import rasterio

from app.models.map import Map

logger = logging.getLogger(__name__)

PNG = "png"
GEOTIFF_WGS84 = "geotiff_wgs84"
GEOTIFF_UTM = "geotiff_utm"

FORMATS = (PNG, GEOTIFF_WGS84, GEOTIFF_UTM)

_SUFFIXES = {
    GEOTIFF_WGS84: "_epsg4326.tif",
    GEOTIFF_UTM: "_utm.tif",
}


def file_extension(fmt: str) -> str:
    """Extension to append to the user supplied download filename."""
    return ".png" if fmt == PNG else ".tif"


def export_map_file(map: Map, fmt: str) -> tuple[str, str]:
    """Return (path_on_disk, media_type) for the requested format.

    Raises ValueError for an unknown format or unusable map data, and
    FileNotFoundError when the source image is missing.
    """
    if fmt not in FORMATS:
        raise ValueError(f"Unsupported format '{fmt}' (expected one of {', '.join(FORMATS)})")

    img_path = map.url
    if not img_path or not os.path.exists(img_path):
        raise FileNotFoundError(f"Map image not found on disk (map_id: {map.id})")

    if fmt == PNG:
        return img_path, "image/png"

    # ODM maps keep WebODM's original, properly projected orthophoto next to the
    # PNG — serve it read-only rather than rebuilding a worse one from the PNG.
    if fmt == GEOTIFF_UTM and map.odm:
        source_tif = str(Path(img_path).with_suffix(".tif"))
        if os.path.exists(source_tif):
            logger.info(f"Serving original ODM orthophoto for map {map.id}: {source_tif}")
            return source_tif, "image/tiff"

    out_path = str(Path(img_path).with_suffix("")) + _SUFFIXES[fmt]

    if _is_up_to_date(out_path, img_path):
        logger.info(f"Reusing cached GeoTIFF for map {map.id}: {out_path}")
        return out_path, "image/tiff"

    bounds = map.bounds or {}
    if fmt == GEOTIFF_WGS84:
        crs, extent = _wgs84_extent(bounds)
    else:
        crs, extent = _utm_extent(bounds)

    logger.info(f"Generating {fmt} for map {map.id} in {crs} -> {out_path}")
    _write_geotiff(img_path, out_path, crs, *extent)
    return out_path, "image/tiff"


def _is_up_to_date(out_path: str, img_path: str) -> bool:
    return os.path.exists(out_path) and os.path.getmtime(out_path) >= os.path.getmtime(img_path)


def _wgs84_extent(bounds: dict) -> tuple[str, tuple[float, float, float, float]]:
    """Axis-aligned lat/lon extent from the map's GPS corners (stored as [lon, lat])."""
    corners = (bounds.get("corners") or {}).get("gps")
    if not corners:
        raise ValueError("Map has no GPS corner bounds — cannot build a WGS84 GeoTIFF")

    lons = [corner[0] for corner in corners]
    lats = [corner[1] for corner in corners]
    return "EPSG:4326", (min(lons), min(lats), max(lons), max(lats))


def _utm_extent(bounds: dict) -> tuple[str, tuple[float, float, float, float]]:
    """Extent in the map's native UTM zone — the projection the raster was built in."""
    utm = bounds.get("utm")
    if not utm:
        raise ValueError("Map has no UTM bounds — cannot build a UTM GeoTIFF")

    try:
        extent = (
            float(utm["easting_min"]),
            float(utm["northing_min"]),
            float(utm["easting_max"]),
            float(utm["northing_max"]),
        )
    except (KeyError, TypeError, ValueError) as e:
        raise ValueError(f"Incomplete UTM bounds on map: {e}")

    return _utm_crs(utm), extent


def _utm_crs(utm: dict) -> str:
    """Resolve the UTM CRS from either stored shape.

    The fast/advanced pipelines store `zone` as an int plus a `hemisphere` letter;
    the ODM pipeline stores the CRS string itself (e.g. "EPSG:32632").
    """
    zone = utm.get("zone")
    if isinstance(zone, str) and zone.upper().startswith("EPSG:"):
        return zone.upper()

    try:
        zone_number = int(zone)
    except (TypeError, ValueError):
        raise ValueError(f"Cannot determine UTM zone from bounds (zone: {zone!r})")

    if not 1 <= zone_number <= 60:
        raise ValueError(f"UTM zone out of range: {zone_number}")

    hemisphere = str(utm.get("hemisphere", "N")).upper()
    base = 32700 if hemisphere.startswith("S") else 32600
    return f"EPSG:{base + zone_number}"


def _write_geotiff(
    img_path: str,
    out_path: str,
    crs: str,
    left: float,
    bottom: float,
    right: float,
    top: float,
) -> None:
    img = cv2.imread(img_path, cv2.IMREAD_UNCHANGED)
    if img is None:
        raise ValueError(f"Could not read map image: {img_path}")

    # rasterio writes RGBA, OpenCV reads BGR(A)
    if img.shape[-1] == 4:
        img = cv2.cvtColor(img, cv2.COLOR_BGRA2RGBA)
    elif img.shape[-1] == 3:
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGBA)
    else:
        raise ValueError(f"Unexpected channel count in map image: {img.shape}")

    height, width = img.shape[:2]
    transform = rasterio.transform.from_bounds(left, bottom, right, top, width, height)

    # Write to a unique temp file and rename, so a concurrent request for the same
    # map never gets served a half-written GeoTIFF.
    tmp_path = f"{out_path}.{os.getpid()}.{threading.get_ident()}.tmp"
    try:
        with rasterio.open(
            tmp_path, "w", driver="GTiff",
            height=height, width=width,
            count=4, dtype=img.dtype.name,
            crs=crs,
            transform=transform,
            compress="DEFLATE",
            tiled=True,
        ) as dst:
            for band in range(4):
                dst.write(img[:, :, band], band + 1)
        os.replace(tmp_path, out_path)
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
