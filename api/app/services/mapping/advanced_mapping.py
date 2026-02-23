"""
advanced_mapping.py — Perspective-correct orthomosaic generation.

Accounts for full camera orientation (yaw, pitch, roll) to compute
perspective ground projections instead of assuming nadir-only viewing.
Uses homography-based warping (cv2.warpPerspective) to place each image
directly onto the map canvas with correct perspective distortion.

Drop-in replacement for fast_mapping.map_images().
"""

import math
import os
import logging
import time

import cv2
import numpy as np
from billiard import Pool
from scipy.spatial import Voronoi


from app.config import config
from app.schemas.image import ImageOut, MappingDataOut
from app.schemas.map import MapCreate, MapElementCreate
from app.schemas.report import ProcessingSettings
from app.services.mapping.progress_updater import ProgressUpdater
from app.services.mapping.fast_mapping import (
    calculate_reference_yaw,
    calc_voronoi_mask,
    save_map_image,
    process_with_timeouts_starmap,
    _calculate_utm_grid_north_diverence,
    _utm_to_lat_lon,
    StarmapTimeoutError,
    BatchTimeoutError,
)
import app.crud.map as crud

logger = logging.getLogger(__name__)
UPLOAD_DIR = config.UPLOAD_DIR


# ---------------------------------------------------------------------------
# MapElement — stores an image's perspective-projected ground footprint
# ---------------------------------------------------------------------------

class MapElement:
    """Represents an image's ground footprint with full perspective geometry."""

    __slots__ = (
        "image_id", "image_path", "utm", "utm_corners", "creation_timestamp",
        "matrix_contains_temperature", "index", "px_corners", "px_center",
        "image_matrix", "use_lower_half",
        "image_width", "image_height",
        "voronoi_gps", "voronoi_image_px",
    )

    def __init__(self, image_id, image_path, utm, utm_corners,
                 creation_timestamp, matrix_contains_temperature,
                 use_lower_half=False, image_width=None, image_height=None):
        self.image_id = image_id
        self.image_path = image_path
        self.utm = utm
        self.utm_corners = utm_corners          # 4 UTM (easting, northing) tuples
        self.creation_timestamp = creation_timestamp
        self.matrix_contains_temperature = matrix_contains_temperature
        self.use_lower_half = use_lower_half    # True if only bottom half is usable
        self.image_width = image_width          # full image width (pixels)
        self.image_height = image_height        # full image height (pixels)
        self.index = None
        self.px_corners = None                  # 4 pixel (x, y) tuples
        self.px_center = None                   # pixel (x, y)
        self.image_matrix = None                # loaded & warped image ROI
        self.voronoi_gps = None                 # [[lat, lon], ...] polygon
        self.voronoi_image_px = None            # [[x, y], ...] in full image space

    def get_bounds(self):
        """Pixel-space bounding box (x1, y1, x2, y2)."""
        xs, ys = zip(*self.px_corners)
        return int(min(xs)), int(min(ys)), int(max(xs)), int(max(ys))

    def get_dims(self):
        x1, y1, x2, y2 = self.get_bounds()
        return x2 - x1, y2 - y1

    def clear_image_matrix(self):
        self.image_matrix = None

    def generate_database_map_element(self, utm_to_latlon, map_id):
        zone = self.utm["zone"]
        hemisphere = self.utm["hemisphere"]

        corners_gps = []
        for e, n in self.utm_corners:
            lon, lat = utm_to_latlon(e, n, zone, hemisphere)
            corners_gps.append((lat, lon))

        coord_gps = utm_to_latlon(
            self.utm["easting"], self.utm["northing"], zone, hemisphere
        )

        return MapElementCreate(
            map_id=map_id,
            image_id=self.image_id,
            index=self.index,
            coord={"utm": self.utm, "gps": coord_gps},
            corners={"utm": self.utm_corners, "gps": corners_gps},
            px_coord={"px": self.px_center},
            px_corners={"px": self.px_corners},
            voronoi_gps=self.voronoi_gps,
            voronoi_image_px=self.voronoi_image_px,
        )


# ---------------------------------------------------------------------------
# 3D geometry — camera rotation & ray-ground intersection
# ---------------------------------------------------------------------------

def _build_camera_rotation(heading_rad, pitch_rad, roll_rad):
    """
    Build a 3x3 rotation matrix: camera frame → world frame (ENU).

    World:  X = East, Y = North, Z = Up
    Camera: X = Right, Y = Down,  Z = Forward (optical axis)

    Args:
        heading_rad: Heading from grid-North, CW positive (radians).
        pitch_rad:   Angle from horizontal, negative = down (rad).
                     -π/2 = nadir (straight down).
        roll_rad:    Rotation around optical axis (rad). 0 = level.
    """
    cy, sy = math.cos(heading_rad), math.sin(heading_rad)
    cp, sp = math.cos(pitch_rad),   math.sin(pitch_rad)
    cr, sr = math.cos(roll_rad),    math.sin(roll_rad)

    # Optical axis direction in world frame
    z_cam = np.array([cp * sy, cp * cy, sp])

    # "Right" without roll — perpendicular to heading in horizontal plane
    x_no_roll = np.array([cy, -sy, 0.0])

    # "Down-in-image" without roll
    y_no_roll = np.cross(z_cam, x_no_roll)
    norm = np.linalg.norm(y_no_roll)
    if norm > 1e-9:
        y_no_roll /= norm

    # Apply roll (rotation around optical axis)
    x_cam = cr * x_no_roll + sr * y_no_roll
    y_cam = -sr * x_no_roll + cr * y_no_roll

    # Columns = camera axes expressed in world coords
    return np.column_stack([x_cam, y_cam, z_cam])


def _ray_ground_intersect(cam_pos, ray_world):
    """
    Intersect a world-frame ray with the z = 0 ground plane.

    Returns (easting, northing) or None if the ray doesn't hit the ground.
    """
    if ray_world[2] >= 0:
        return None  # ray parallel or pointing upward
    t = -cam_pos[2] / ray_world[2]
    return (cam_pos[0] + t * ray_world[0],
            cam_pos[1] + t * ray_world[1])


# ---------------------------------------------------------------------------
# Ground footprint computation (runs in worker pool)
# ---------------------------------------------------------------------------

def _compute_ground_footprint(image_dict, reference_yaw):
    """
    Compute perspective-correct ground projection of image corners.

    Casts rays from the camera through each image corner, intersects
    with the z = 0 ground plane, producing a quadrilateral footprint.
    For nadir images (pitch ≈ -90°) this reduces to the same rectangular
    footprint as fast_mapping.
    """
    md = image_dict["mapping_data"]
    thermal = image_dict["thermal"]
    width = image_dict["width"]
    height = image_dict["height"]
    fov = md["fov"]
    altitude = md["rel_altitude"]
    utm = image_dict["coord"]["utm"]
    gps = image_dict["coord"]["gps"]

    # Camera position in world (ENU)
    cam_pos = np.array([utm["easting"], utm["northing"], float(altitude)])

    # Camera intrinsics (pinhole)
    diag_px = math.sqrt(width ** 2 + height ** 2)
    focal_px = diag_px / (2.0 * math.tan(math.radians(fov / 2.0)))

    # Orientation angles
    cam_yaw_rad = math.radians(md["cam_yaw"])
    cam_pitch_rad = math.radians(md["cam_pitch"])           # -90° = nadir
    cam_roll_rad = math.radians(md.get("cam_roll") or 0.0)

    north_div = _calculate_utm_grid_north_diverence(
        utm["zone"], gps["lat"], gps["lon"]
    )

    # Grid heading: true heading corrected for UTM grid convergence
    heading_rad = cam_yaw_rad + reference_yaw - north_div

    R = _build_camera_rotation(heading_rad, cam_pitch_rad, cam_roll_rad)

    # Project each image corner onto the ground
    cx, cy_img = width / 2.0, height / 2.0
    corners_px = [(0, 0), (width, 0), (width, height), (0, height)]

    utm_corners = []
    fallback_needed = False
    for u, v in corners_px:
        d_cam = np.array([(u - cx) / focal_px, (v - cy_img) / focal_px, 1.0])
        d_world = R @ d_cam

        hit = _ray_ground_intersect(cam_pos, d_world)
        if hit is None:
            fallback_needed = True
            # Nudge ray downward so it eventually hits the ground
            d_world[2] = -1e-3
            hit = _ray_ground_intersect(cam_pos, d_world)
        utm_corners.append(hit)

    # Sanity check: reject footprints > 20× the nadir footprint diagonal
    nadir_diag_m = 2.0 * math.tan(math.radians(fov / 2.0)) * altitude
    max_dist = 20.0 * nadir_diag_m
    use_lower_half = False

    def _footprint_too_large(corners):
        for e, n in corners:
            if abs(e - cam_pos[0]) > max_dist or abs(n - cam_pos[1]) > max_dist:
                return True
        return False

    if _footprint_too_large(utm_corners):
        # Try lower half of image (ground-facing portion for tilted gimbals)
        half_h = height / 2.0
        half_corners_px = [
            (0, half_h), (width, half_h), (width, height), (0, height)
        ]
        half_utm_corners = []
        for u, v in half_corners_px:
            d_cam = np.array([(u - cx) / focal_px, (v - cy_img) / focal_px, 1.0])
            d_world = R @ d_cam
            hit = _ray_ground_intersect(cam_pos, d_world)
            if hit is None:
                d_world[2] = -1e-3
                hit = _ray_ground_intersect(cam_pos, d_world)
            half_utm_corners.append(hit)

        if _footprint_too_large(half_utm_corners):
            logger.warning(
                f"Image {image_dict['id']}: footprint too large even with "
                f"lower half (>{max_dist:.0f}m from camera), skipping"
            )
            return None
        else:
            logger.info(
                f"Image {image_dict['id']}: using lower half — full footprint "
                f"exceeded {max_dist:.0f}m limit"
            )
            utm_corners = half_utm_corners
            use_lower_half = True

    # Resolve thermal path
    matrix_contains_temperature = False
    path = image_dict["url"]
    if thermal:
        try:
            td = image_dict.get("thermal_data") or {}
            temp_path = td.get("temp_matrix_path")
            if temp_path and os.path.exists(temp_path):
                matrix_contains_temperature = True
                path = temp_path
        except Exception:
            pass

    return MapElement(
        image_id=image_dict["id"],
        image_path=path,
        utm=utm,
        utm_corners=utm_corners,
        creation_timestamp=image_dict["created_at"],
        matrix_contains_temperature=matrix_contains_temperature,
        use_lower_half=use_lower_half,
        image_width=width,
        image_height=height,
    )


# ---------------------------------------------------------------------------
# Coordinate conversion: UTM footprints → pixel coordinates
# ---------------------------------------------------------------------------

def _calculate_px_coords(elements, target_resolution):
    """Convert UTM corner coords to pixel coords on the map canvas."""
    all_corners = []
    for el in elements:
        all_corners.extend(el.utm_corners)

    eastings, northings = zip(*all_corners)
    min_e, max_e = min(eastings), max(eastings)
    min_n, max_n = min(northings), max(northings)

    span = max(max_e - min_e, max_n - min_n)
    scale = target_resolution / span if span > 0 else 1.0

    map_w = int((max_e - min_e) * scale + 10)
    map_h = int((max_n - min_n) * scale + 10)

    for el in elements:
        el.px_corners = [
            (int((e - min_e) * scale), map_h - int((n - min_n) * scale))
            for e, n in el.utm_corners
        ]
        el.px_center = (
            int(sum(px[0] for px in el.px_corners) / 4),
            int(sum(px[1] for px in el.px_corners) / 4)
        )

    return map_w, map_h, scale, min_e, min_n


# ---------------------------------------------------------------------------
# Image loading & perspective warp (runs in worker pool)
# ---------------------------------------------------------------------------

def _load_and_warp_image(element):
    """
    Load an image and warp it into its map-pixel footprint via
    cv2.getPerspectiveTransform + cv2.warpPerspective.

    This replaces the old resize → rotate → resize pipeline with a single
    perspective warp that correctly handles non-nadir viewing angles.
    """
    # --- Load ---
    image = None
    if element.image_path.endswith(".npy"):
        try:
            image = np.load(element.image_path)
            if image.ndim == 2:
                image = np.dstack((image,) * 3)
        except Exception as e:
            logger.error(f"Failed to load npy {element.image_path}: {e}")

    if image is None:
        image = cv2.imread(element.image_path, cv2.IMREAD_UNCHANGED)
        if image is None:
            logger.error(f"Failed to load image {element.image_path}")
            return element

    # Add alpha channel
    if image.ndim == 2:
        image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGRA)
    elif image.shape[2] == 3:
        image = cv2.cvtColor(image, cv2.COLOR_BGR2BGRA)

    h, w = image.shape[:2]

    # Crop to lower half if the full footprint was too large
    if element.use_lower_half:
        image = image[h // 2:, :]
        h = image.shape[0]

    # --- Perspective warp to ROI ---
    x1, y1, x2, y2 = element.get_bounds()
    roi_w, roi_h = x2 - x1, y2 - y1
    if roi_w <= 0 or roi_h <= 0:
        return element

    src_pts = np.float32([[0, 0], [w, 0], [w, h], [0, h]])
    dst_pts = np.float32([(px - x1, py - y1) for px, py in element.px_corners])

    H = cv2.getPerspectiveTransform(src_pts, dst_pts)
    interp = cv2.INTER_NEAREST if element.matrix_contains_temperature else cv2.INTER_LINEAR

    element.image_matrix = cv2.warpPerspective(
        image, H, (roi_w, roi_h),
        flags=interp,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(0, 0, 0, 0),
    )

    return element


def _process_batch(pool, batch, timeout=5):
    """Load and warp a batch of images in parallel."""
    async_results = [
        pool.apply_async(_load_and_warp_image, (el,)) for el in batch
    ]
    results = []
    timed_out_count = 0
    for i, ar in enumerate(async_results):
        try:
            results.append(ar.get(timeout=timeout))
        except TimeoutError:
            logger.warning(f"Timeout loading element {i} in batch")
            timed_out_count += 1
            results.append(batch[i])  # element without image_matrix
        except Exception as e:
            logger.error(f"Error loading element {i} in batch: {e}")
            results.append(batch[i])

    if timed_out_count:
        raise BatchTimeoutError(results, timed_out_count)
    return results


# ---------------------------------------------------------------------------
# Map compositing
# ---------------------------------------------------------------------------

def _draw_map(elements, voronoi_mask, map_w, map_h, progress_updater):
    """Composite perspective-warped images using Voronoi seam selection."""
    thermal = elements[0].matrix_contains_temperature if elements else False
    dtype = np.float32 if thermal else np.uint8
    map_img = np.zeros((map_h, map_w, 4), dtype=dtype)

    batch_size = 32
    batches = [elements[i:i + batch_size]
               for i in range(0, len(elements), batch_size)]

    MAX_RETRIES = 3
    pool = Pool(processes=8)
    try:
        for bi, batch in enumerate(batches):
            logger.info(f"Starting batch {bi + 1}/{len(batches)}")

            for attempt in range(MAX_RETRIES):
                try:
                    warped = _process_batch(pool, batch)
                    break
                except BatchTimeoutError as e:
                    logger.warning(
                        f"Batch {bi + 1}: {e.timed_out_count} item(s) timed out, "
                        f"replacing pool and using partial results"
                    )
                    warped = e.results
                    pool.terminate()
                    pool.join()
                    pool = Pool(processes=8)
                    break  # use partial results, don't retry
                except Exception as e:
                    logger.error(
                        f"Batch {bi + 1} attempt {attempt + 1} failed: {e}"
                    )
                    pool.terminate()
                    pool.join()
                    pool = Pool(processes=8)
                if attempt == MAX_RETRIES - 1:
                    raise TimeoutError(
                        f"Batch {bi + 1} failed after {MAX_RETRIES} retries"
                    )

            logger.info(f"Completed loading batch {bi + 1}")
            progress_updater.update_progress_of_map(
                "processing", 50 + (bi + 1) / len(batches) * 40
            )

            for el in warped:
                if el.image_matrix is None:
                    logger.warning(
                        f"Skipping element {el.image_id} — image failed to load"
                    )
                    continue

                x1, y1, x2, y2 = el.get_bounds()

                # Clamp ROI to map bounds
                mx1, my1 = max(x1, 0), max(y1, 0)
                mx2, my2 = min(x2, map_w), min(y2, map_h)
                if mx2 <= mx1 or my2 <= my1:
                    el.clear_image_matrix()
                    continue

                # Slice into warped image (offset from ROI origin)
                ix1, iy1 = mx1 - x1, my1 - y1
                image = el.image_matrix[iy1:iy1 + (my2 - my1),
                                        ix1:ix1 + (mx2 - mx1)]

                voronoi_roi = voronoi_mask[my1:my2, mx1:mx2]

                if thermal:
                    existing = map_img[my1:my2, mx1:mx2]
                    is_voronoi = voronoi_roi == el.index
                    undrawn = existing[:, :, 3] == 0
                    img_has_data = image[:, :, 3] > 0
                    existing_much_hotter = (
                        existing[:, :, 0] >= image[:, :, 0] + 20
                    )
                    image_much_hotter = (
                        image[:, :, 0] >= existing[:, :, 0] + 20
                    )

                    use_image = np.zeros_like(is_voronoi)
                    use_image |= is_voronoi & img_has_data
                    use_image |= ~is_voronoi & img_has_data & image_much_hotter
                    use_image &= ~existing_much_hotter
                    use_image |= undrawn & img_has_data

                    mask = use_image[:, :, np.newaxis]
                    map_img[my1:my2, mx1:mx2] = np.where(
                        mask, image, existing
                    )
                else:
                    existing = map_img[my1:my2, mx1:mx2]
                    is_voronoi = voronoi_roi == el.index
                    undrawn = existing[:, :, 3] == 0
                    img_has_data = image[:, :, 3] > 0
                    use_image = (is_voronoi | undrawn) & img_has_data
                    mask = use_image[:, :, np.newaxis]
                    map_img[my1:my2, mx1:mx2] = np.where(
                        mask, image, existing
                    )

                el.clear_image_matrix()

            progress_updater.update_progress_of_map(
                "processing", 50 + (bi + 1) / len(batches) * 45
            )
    finally:
        pool.terminate()
        pool.join()

    # Convert thermal float map to coloured uint8
    if thermal:
        alpha = map_img[:, :, 3]
        temp = map_img[:, :, 0]
        t_max, t_min = np.max(temp), np.min(temp)
        if t_min < 0:
            temp = np.where(temp < 0, temp / 3, temp)
            t_min = np.min(temp)
        factor = 255.0 / (t_max - t_min) if t_max != t_min else 0
        temp_u8 = ((temp - t_min) * factor).astype(np.uint8)
        map_img = cv2.cvtColor(temp_u8, cv2.COLOR_GRAY2BGRA)
        map_img[:, :, 3] = (alpha * 255).astype(np.uint8)

    return map_img


# ---------------------------------------------------------------------------
# Map bounds
# ---------------------------------------------------------------------------

def _find_map_bounds(elements):
    """Compute GPS and UTM bounds from all element corners."""
    all_corners = []
    for el in elements:
        all_corners.extend(el.utm_corners)

    eastings, northings = zip(*all_corners)
    min_e, max_e = min(eastings), max(eastings)
    min_n, max_n = min(northings), max(northings)

    zone = elements[0].utm["zone"]
    hemisphere = elements[0].utm["hemisphere"]

    corners_utm = [
        (min_e, max_n), (max_e, max_n), (max_e, min_n), (min_e, min_n)
    ]
    corners_gps = []
    for e, n in corners_utm:
        lon, lat = _utm_to_lat_lon(e, n, zone, hemisphere)
        corners_gps.append((lon, lat))

    min_ll = _utm_to_lat_lon(min_e, min_n, zone, hemisphere)
    max_ll = _utm_to_lat_lon(max_e, max_n, zone, hemisphere)

    return {
        "gps": {
            "latitude_min": min_ll[1],
            "latitude_max": max_ll[1],
            "longitude_min": min_ll[0],
            "longitude_max": max_ll[0],
        },
        "utm": {
            "northing_min": min_n,
            "northing_max": max_n,
            "easting_min": min_e,
            "easting_max": max_e,
            "zone": zone,
            "hemisphere": hemisphere,
        },
        "corners": {"utm": corners_utm, "gps": corners_gps},
    }


# ---------------------------------------------------------------------------
# Voronoi polygon helpers
# ---------------------------------------------------------------------------

def _compute_voronoi_polygons(elements, map_w, map_h):
    """
    Compute vector Voronoi cell polygon for each element in pixel space,
    clipped to the map canvas [0, map_w] × [0, map_h].

    Returns a list of polygon vertex lists ([[x,y],...]) or None entries
    for cells that are empty after clipping.
    """
    map_bounds = [[0, 0], [map_w, 0], [map_w, map_h], [0, map_h]]

    if len(elements) == 0:
        return []
    if len(elements) == 1:
        return [map_bounds]

    pts = np.array([[el.px_center[0], el.px_center[1]] for el in elements],
                   dtype=np.float64)
    far = max(map_w, map_h) * 10.0
    padding = np.array([
        [-far, -far],
        [map_w + far, -far],
        [-far, map_h + far],
        [map_w + far, map_h + far],
    ], dtype=np.float64)
    all_pts = np.vstack([pts, padding])

    vor = Voronoi(all_pts)
    result = []
    for i in range(len(elements)):
        region_idx = vor.point_region[i]
        region = vor.regions[region_idx]
        if not region or -1 in region:
            poly = None
        else:
            poly = _sutherland_hodgman(vor.vertices[region].tolist(), map_bounds)
            if len(poly) < 3:
                poly = None
        result.append(poly)
    return result


def _sutherland_hodgman(subject, clip):
    """
    Clip a convex subject polygon against a convex clip polygon.

    Both are sequences of [x, y] pairs (or indexable 2-tuples).
    The clip polygon is normalised to CCW winding before clipping.
    Returns a list of [x, y] pairs, possibly empty.
    """
    def _inside(p, a, b):
        # True if p is on the left of (or on) directed edge a→b (CCW convention)
        return ((b[0] - a[0]) * (p[1] - a[1])
                - (b[1] - a[1]) * (p[0] - a[0])) >= 0

    def _intersect(p1, p2, p3, p4):
        dx12 = p2[0] - p1[0]; dy12 = p2[1] - p1[1]
        dx34 = p4[0] - p3[0]; dy34 = p4[1] - p3[1]
        denom = dx12 * dy34 - dy12 * dx34
        if abs(denom) < 1e-10:
            return [p2[0], p2[1]]
        t = ((p3[0] - p1[0]) * dy34 - (p3[1] - p1[1]) * dx34) / denom
        return [p1[0] + t * dx12, p1[1] + t * dy12]

    clip = [list(v) for v in clip]
    # Ensure CCW winding (signed area > 0 in standard math coords)
    n = len(clip)
    area = sum(clip[i][0] * clip[(i + 1) % n][1]
               - clip[(i + 1) % n][0] * clip[i][1]
               for i in range(n))
    if area < 0:
        clip = list(reversed(clip))

    output = [list(v) for v in subject]
    if not output:
        return []

    for i in range(len(clip)):
        if not output:
            break
        input_list = output
        output = []
        a = clip[i]
        b = clip[(i + 1) % len(clip)]
        for j in range(len(input_list)):
            curr = input_list[j]
            prev = input_list[j - 1]
            if _inside(curr, a, b):
                if not _inside(prev, a, b):
                    output.append(_intersect(prev, curr, a, b))
                output.append(curr)
            elif _inside(prev, a, b):
                output.append(_intersect(prev, curr, a, b))

    return output


def _voronoi_poly_to_gps(polygon, scale, min_e, min_n, map_h, zone, hemisphere):
    """Convert Voronoi pixel polygon to GPS [[lat, lon], ...] list."""
    result = []
    for x, y in polygon:
        e = x / scale + min_e
        n = (map_h - y) / scale + min_n
        lon, lat = _utm_to_lat_lon(e, n, zone, hemisphere)
        result.append([lat, lon])
    return result


def _voronoi_poly_to_image_px(polygon, element):
    """
    Map a Voronoi pixel polygon back into the original image's pixel space.

    1. Clips the polygon to the element's footprint (px_corners).
    2. Builds the same perspective homography used in _load_and_warp_image.
    3. Inverts H and back-projects clipped vertices to image pixel coords.
    4. If use_lower_half, adds image_height//2 to convert to full-image coords.

    Returns [[x, y], ...] or None if the clipped polygon is degenerate.
    """
    if element.image_width is None or element.image_height is None:
        return None

    clipped = _sutherland_hodgman(polygon, element.px_corners)
    if len(clipped) < 3:
        return None

    w = element.image_width
    h = element.image_height // 2 if element.use_lower_half else element.image_height
    x1, y1, x2, y2 = element.get_bounds()

    src_pts = np.float32([[0, 0], [w, 0], [w, h], [0, h]])
    dst_pts = np.float32([(px - x1, py - y1) for px, py in element.px_corners])

    H = cv2.getPerspectiveTransform(src_pts, dst_pts)
    _, H_inv = cv2.invert(H)

    pts = np.array([[x - x1, y - y1] for x, y in clipped],
                   dtype=np.float32).reshape(-1, 1, 2)
    img_pts = cv2.perspectiveTransform(pts, H_inv).reshape(-1, 2)

    if element.use_lower_half:
        img_pts[:, 1] += element.image_height // 2

    return img_pts.tolist()


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def map_images_advanced(report_id, mapping_report_id, mapping_selection, settings,
               db, progress_updater, map_index=0):
    """
    Generate an orthomosaic with perspective-correct ground projection.

    Drop-in replacement for fast_mapping.map_images() — same signature,
    same database outputs (Map + MapElement rows).
    """
    settings = (settings.dict() if isinstance(settings, ProcessingSettings)
                else settings)
    progress_updater.update_progress_of_map("processing", 1.0)

    # Serialize ORM images to dicts (required for multiprocessing)
    dicts = []
    for image in mapping_selection["images"]:
        md_out = (MappingDataOut.from_orm(image.mapping_data)
                  if image.mapping_data else None)
        img_dict = ImageOut.from_orm(image).dict()
        img_dict["mapping_data"] = md_out.dict() if md_out else None
        dicts.append(img_dict)
    progress_updater.update_progress_of_map("processing", 3.0)

    # Reference yaw from trajectory analysis
    reference_yaw = calculate_reference_yaw(mapping_selection["images"])

    # Compute ground footprints in parallel
    params = [(d, reference_yaw) for d in dicts]
    MAX_RETRIES = 3
    for attempt in range(MAX_RETRIES):
        with Pool(processes=8) as pool:
            try:
                elements = process_with_timeouts_starmap(
                    pool, _compute_ground_footprint, params, timeout_per_item=2
                )
                break
            except StarmapTimeoutError as e:
                logger.warning(
                    f"Attempt {attempt + 1}: {len(e.timed_out_indices)} footprint(s) "
                    f"timed out, using partial results"
                )
                elements = e.results
                break  # pool terminated by context manager, use partial results
            except Exception as e:
                logger.error(
                    f"Ground footprint attempt {attempt + 1} failed: {e}"
                )
                pool.terminate()
                pool.join()
        if attempt == MAX_RETRIES - 1:
            raise TimeoutError("Failed to compute ground footprints")

    elements = [e for e in elements if e is not None]
    for i, el in enumerate(elements):
        el.index = i
    progress_updater.update_progress_of_map("processing", 20.0)

    # Bounds
    bounds = _find_map_bounds(elements)
    progress_updater.update_progress_of_map("processing", 25.0)

    # Pixel coordinates
    map_w, map_h, scale, min_e, min_n = _calculate_px_coords(
        elements, settings["target_map_resolution"]
    )
    progress_updater.update_progress_of_map("processing", 30.0)

    # Voronoi seam mask (reuse from fast_mapping — same algorithm)
    voronoi = calc_voronoi_mask(elements, map_w, map_h, performance_factor=8)
    progress_updater.update_progress_of_map("processing", 50.0)

    time_a = time.time()
    # Compute vector Voronoi cell polygons
    voronoi_polygons = _compute_voronoi_polygons(elements, map_w, map_h)
    zone = elements[0].utm["zone"]
    hemi = elements[0].utm["hemisphere"]
    for i, el in enumerate(elements):
        poly = voronoi_polygons[i]
        if poly is None:
            continue
        el.voronoi_gps = _voronoi_poly_to_gps(
            poly, scale, min_e, min_n, map_h, zone, hemi
        )
        el.voronoi_image_px = _voronoi_poly_to_image_px(poly, el)
    time_b = time.time()
    logger.warning(f"===============> Voronoi polygon computation took {time_b - time_a:.1f} seconds")

    # Composite
    map_img = _draw_map(elements, voronoi, map_w, map_h, progress_updater)

    # Save
    file_path = (UPLOAD_DIR / str(report_id)
                 / f"final_map_{map_index}_{int(time.time())}.png")
    save_map_image(map_img, file_path)
    logger.info(f"Advanced map for report {report_id} saved as {file_path}")

    # Database: Map
    map_data = MapCreate(
        mapping_report_id=mapping_report_id,
        name=f"advanced_{mapping_selection['type']}_{map_index}",
        url=str(file_path),
        odm=False,
        bounds=bounds,
    )
    db_map = crud.create(db, map_data)

    # Database: MapElements
    db_elements = [
        el.generate_database_map_element(_utm_to_lat_lon, db_map.id)
        for el in elements
    ]
    logger.info(
        f"Storing {len(db_elements)} map elements for map {db_map.id}"
    )
    crud.create_multiple_map_elements(db, db_map.id, db_elements)

    progress_updater.update_progress_of_map("processing", 100.0)
