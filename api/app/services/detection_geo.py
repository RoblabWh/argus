"""Georeferencing helpers for individual detections.

A detection's GPS position is interpolated from the 4 ground corners of its
source image, which the mapping pipeline records on the image's ``MapElement``.
The interpolation lives here rather than in ``fire_map`` because three callers
now need it: the fire overlay, the manual-detection create endpoint, and
(indirectly, via the same convention) the YOLO reID worker.
"""

from sqlalchemy.orm import Session

from app import models


def interpolate_px_to_gps(px: float, py: float, width: int, height: int, corners_gps,
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


def get_image_footprint(db: Session, image_id: int):
    """The image's ground footprint as ``(corners_gps, src_px)``, or ``(None, None)``.

    Corners live on the MapElement written during mapping, so this returns
    nothing for an image that has not been mapped (or was excluded from the
    mosaic). A report can own several maps — RGB and thermal — so the first
    element carrying usable corners wins, matching get_reid_input.
    """
    elements = (
        db.query(models.MapElement)
        .filter(models.MapElement.image_id == image_id)
        .all()
    )
    for el in elements:
        gps = (el.corners or {}).get("gps") if el.corners else None
        if gps and len(gps) == 4:
            src_px = (el.corners or {}).get("src_px")
            return gps, (src_px if src_px and len(src_px) == 4 else None)
    return None, None


def estimate_detection_gps(db: Session, image, bbox) -> dict | None:
    """Estimate a detection's coordinate from its bbox centre.

    ``bbox`` is [x, y, w, h] in source-image pixels. Returns the ``coord`` shape
    the frontend and the DRZ share dialog read (``{"gps": {"lat", "lon"}}``), or
    None when the image has no footprint or the inputs are unusable.
    """
    if not bbox or len(bbox) != 4 or not image.width or not image.height:
        return None

    corners_gps, src_px = get_image_footprint(db, image.id)
    if not corners_gps:
        return None

    x, y, w, h = (float(v) for v in bbox)
    lat, lon = interpolate_px_to_gps(
        x + w / 2, y + h / 2, image.width, image.height, corners_gps, src_px
    )
    return {"gps": {"lat": lat, "lon": lon}}
