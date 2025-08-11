import os
import math
import cv2
import imutils
import numpy as np
from app.config import UPLOAD_DIR
from app.schemas.image import ImageOut, MappingDataOut
from app.schemas.map import MapCreate, MapElementCreate
from app.schemas.report import ProcessingSettings
from app.services.mapping.progress_updater import ProgressUpdater
import app.crud.map as crud
import logging

import billiard as multiprocessing
from billiard import Pool

logger = logging.getLogger(__name__)

class Map_Element:
    def __init__(self, utm, utm_corners, rotation, image_path, image_width, creation_timestamp, image_id):
        """
        Initializes a Map_Element with the given parameters.
        """
        self.utm = utm
        self.utm_corners = utm_corners
        self.rotation = rotation
        self.image_path = image_path
        self.image_width = image_width
        self.creation_timestamp = creation_timestamp
        self.image_id = image_id
        self.px_corners = None  # Placeholder for pixel corners calculation
        self.px_center = None  # Placeholder for pixel center calculation
        self.scale = None  # Placeholder for scale calculation
        self.index = None  # Placeholder for index in the map
        self.image_matrix = None  # Placeholder for image matrix calculation

    def get_bounds(self):
        """
        Calculates the bounding box of the map element based on pixel corners.
        Returns:
            tuple: (x1, y1, x2, y2) coordinates of the bounding box.
        """
        if not self.px_corners:
            raise ValueError("Pixel corners not calculated.")
        x_coords, y_coords = zip(*self.px_corners)
        return int(min(x_coords)), int(min(y_coords)), int(max(x_coords)), int(max(y_coords))
    
    def get_dims(self):
        """
        Calculates the dimensions of the map element based on pixel corners.
        Returns:
            tuple: (width, height) of the map element.
        """
        if not self.px_corners:
            raise ValueError("Pixel corners not calculated.")
        x_coords, y_coords = zip(*self.px_corners)
        return int(max(x_coords) - min(x_coords)), int(max(y_coords) - min(y_coords))

    def clear_image_matrix(self):
        """
        Clears the image matrix to free memory.
        """
        self.image_matrix = None
        logger.debug(f"Cleared image matrix for element with UTM: {self.utm}")

    def generate_database_map_element(self, utm_conversion_callable, map_id) -> MapElementCreate:
        """
        Generates a MapElementCreate schema instance for database storage.
        Returns:
            MapElementCreate: An instance of MapElementCreate with the current element's data.
        """

        corners_gps = []
        zone = self.utm['zone']
        hemisphere = self.utm['hemisphere']
        for corner in self.utm_corners:
            gps_lon, gps_lat = utm_conversion_callable(corner[0], corner[1], zone, hemisphere)
            corners_gps.append(( gps_lat, gps_lon))

        coord_gps = utm_conversion_callable(self.utm['easting'], self.utm['northing'], zone, hemisphere)

        return MapElementCreate(
            map_id=map_id,
            image_id=self.image_id,
            index=self.index,
            coord={"utm": self.utm, "gps": coord_gps},
            corners={"utm": self.utm_corners, "gps": corners_gps},
            px_coord={"px": self.px_center},
            px_corners={"px": self.px_corners}
        )




def map_images(report_id: int, mapping_report_id: int, mapping_selection: dict, settings: dict, db, progress_updater: ProgressUpdater, map_index=0):
    settings = settings.dict() if isinstance(settings, ProcessingSettings) else settings
    progress_updater.update_progress_of_map("processing", 1.0)

    # loading all mapping data for the images
    dicts = []
    for image in mapping_selection['images']:
        if image.mapping_data:
            mapping_data_out = MappingDataOut.from_orm(image.mapping_data)
        else:
            mapping_data_out = None

        image_dict = ImageOut.from_orm(image).dict()
        image_dict["mapping_data"] = mapping_data_out.dict() if mapping_data_out else None
        dicts.append(image_dict)
    progress_updater.update_progress_of_map("processing", 3.0)


    # Calculate the reference yaw based on the images in the mapping selection 
    reference_yaw = calculate_reference_yaw(mapping_selection['images'])

    # generating map elements from the images (with a safer parallel pool)
    MAX_RETRIES = 3
    TIMEOUT_PER_ITEM = 2  # seconds
    params = [(image, reference_yaw) for image in dicts]
    
    for attempt in range(MAX_RETRIES):
        logger.info(f"Attempt {attempt + 1} to calculate UTM corners")
        with Pool(processes=8) as pool:
            try:
                map_elements = process_with_timeouts_starmap(pool, calculate_utm_corners, params, TIMEOUT_PER_ITEM)
                break  # success
            except Exception as e:
                logger.error(f"Failure in starmap attempt {attempt + 1}: {e}")
                pool.terminate()
                pool.join()

        if attempt == MAX_RETRIES - 1:
            logger.error("Failed to generate map elements after all retries")
            raise TimeoutError("Giving up on calculate_utm_corners")

    
    for i, element in enumerate(map_elements):
        element.index = i
    progress_updater.update_progress_of_map("processing", 20.0)

    
    # determine the bounds of the map based on the map elements (based on utm image corners)
    bounds = _find_map_bounds(map_elements)
    progress_updater.update_progress_of_map("processing", 25.0)

    # convert the map elements to pixel coordinates based the target resolution
    map_width, map_height = calculate_px_coords(map_elements, settings['target_map_resolution'])
    progress_updater.update_progress_of_map("processing", 30.0)

    # testing cv and file saving
    # map_img = draw_test_map(map_elements, map_width, map_height)
    # file_path = UPLOAD_DIR / str(report_id) / f"map_{map_index}.png"
    # save_map_image(map_img, file_path)
    # logger.info(f"Map image for report {report_id} saved as {file_path}")

    # calculating images masks with the voronoi algorithm on a downscaled version of the map
    file_path = UPLOAD_DIR / str(report_id) / f"voronoi_{map_index}.png"
    voronoi = calc_voronoi_mask(map_elements, map_width, map_height, performance_factor=8)#, debug_save_path=file_path)
    progress_updater.update_progress_of_map("processing", 50.0)



    # draw map in batches combining map elements and voronoi mask
    map = draw_map(map_elements, voronoi, map_width, map_height, progress_updater)
    file_path = UPLOAD_DIR / str(report_id) / f"final_map_{map_index}.png"
    save_map_image(map, file_path)
    logger.info(f"Final map for report {report_id} saved as {file_path}")


    #store map data in database
    map_data = MapCreate(
        mapping_report_id=mapping_report_id,
        name=f"fast_{mapping_selection['type']}_{map_index}",
        url=str(file_path),
        odm=False,
        bounds=bounds
    )
    logger.info(f"Creating map in database for report {report_id} with data: {map_data}")
    map = crud.create(db, map_data)


    # store map elements in database
    map_elements_to_store = [element.generate_database_map_element(_utm_to_lat_lon, map.id) for element in map_elements]
    logger.info(f"Storing {len(map_elements_to_store)} map elements in database for map {map.id}")
    crud.create_multiple_map_elements(db, map.id, map_elements_to_store)

    progress_updater.update_progress_of_map("processing", 100.0)


def process_with_timeouts_starmap(pool, func, params, timeout_per_item=5):
    results = []
    async_results = []

    for param in params:
        res = pool.apply_async(func, args=param)
        async_results.append(res)

    for i, res in enumerate(async_results):
        try:
            result = res.get(timeout=timeout_per_item)
            results.append(result)
        except TimeoutError:
            logger.warning(f"Timeout processing item {i} with params {params[i]}")
            results.append(None)  # or use params[i] or a custom error placeholder
        except Exception as e:
            logger.error(f"Error processing item {i} with params {params[i]}: {e}")
            results.append(None)  # or log/handle differently
    return results

    


def calculate_reference_yaw(images: list[ImageOut]) -> float:
    margin_orientation_degrees = 1.5
    margin_trajectory_degrees = 5

    images_len = len(images)
    if images_len < 3:
        dumb_offset = calc_dumb_offset(images[0]) #uav yaw - cam yaw
        logger.info(f"REFERENCE YAW, using dumb offset: {dumb_offset}")
        return math.radians(dumb_offset)


    for i in range(len(images)-2):
        roi = images[i:i+3]

        time_deltas = images[i+1].created_at - images[i].created_at, images[i+2].created_at - images[i+1].created_at
        # logger.info(f"time deltas: {time_deltas}")

        orientation_diff_degrees = roi[0].mapping_data.cam_yaw - roi[1].mapping_data.cam_yaw
        if orientation_diff_degrees > margin_orientation_degrees:
            continue

        orientation_diff_degrees = roi[1].mapping_data.cam_yaw - roi[2].mapping_data.cam_yaw
        if orientation_diff_degrees > margin_orientation_degrees:
            continue
        
        northing1 = float(roi[0].coord['utm']['northing'])
        easting1 = float(roi[0].coord['utm']['easting'])
        northing2 = float(roi[1].coord['utm']['northing'])
        easting2 = float(roi[1].coord['utm']['easting'])
        northing3 = float(roi[2].coord['utm']['northing'])
        easting3 = float(roi[2].coord['utm']['easting'])
        # logger.info(f"Coordinates: {northing1}, {easting1} | {northing2}, {easting2} | {northing3}, {easting3}")

        v_diff_a = np.array((easting2, northing2)) - np.array((easting1, northing1))
        v_diff_b = np.array((easting3, northing3)) - np.array((easting2, northing2))
        if np.linalg.norm(v_diff_a) == 0 or  np.linalg.norm(v_diff_b) == 0: 
            logger.warning("Zero vector encountered in trajectory calculation, skipping this set of images.")
            continue
        angle = np.arccos(np.dot(v_diff_a, v_diff_b) / (np.linalg.norm(v_diff_a) * np.linalg.norm(v_diff_b)))
        angle = np.degrees(angle)
        if angle < margin_trajectory_degrees:
            reference_yaw = np.arctan2(v_diff_b[0], v_diff_b[1])
            reference_yaw = np.degrees(reference_yaw)
            reference_yaw = reference_yaw - roi[1].mapping_data.cam_yaw
            logger.info(f"REFERENCE YAW, with refined calculation: {reference_yaw} using images {i}, {i+1}, {i+2}")
            # logger.info(f"images: {roi[0].filename}, {roi[1].filename}, {roi[2].filename}")
            return math.radians(float(reference_yaw))
    return calc_dumb_offset(images[0])


def calc_dumb_offset(image: ImageOut) -> float:
    if not image.mapping_data or not image.mapping_data.cam_yaw:
        return 0.0
    return image.mapping_data.uav_yaw - image.mapping_data.cam_yaw



def calculate_utm_corners(image: ImageOut, reference_yaw: float) -> Map_Element:
    fov = image["mapping_data"]["fov"]
    rel_altitude = image["mapping_data"]["rel_altitude"]
    uav_yaw = -1 * math.radians(image["mapping_data"]["uav_yaw"]) 
    cam_yaw = -1 * (math.radians(image["mapping_data"]["cam_yaw"]) + reference_yaw)
    width = image["width"]
    height = image["height"]
    utm = image["coord"]["utm"]
    path = image["url"]
    creation_timestamp = image["created_at"]
    north_divergence = _calculate_utm_grid_north_diverence(utm["zone"], image["coord"]['gps']['lat'], image["coord"]['gps']['lon'])
    orientation = cam_yaw + north_divergence

    diag_length_px = (width**2 + height**2)**0.5
    diag_length_m = 2 * math.tan(math.radians(fov / 2)) * rel_altitude 
    scale = diag_length_m / diag_length_px 
    
    #rotate all corners of the image by the uav orientation
    w_half = width / 2
    h_half = height / 2
    corners = [
        (w_half, h_half),  # Top-left
        (w_half, -h_half),  # Bottom-left
        (-w_half, -h_half),  # Bottom-right
        (-w_half, h_half)   # Top-right
    ]
    rotated_corners = []
    for corner in corners:
        x, y = corner
        # Rotate around the center of the image
        x_rotated = x * math.cos(orientation) - y * math.sin(orientation)
        y_rotated = x * math.sin(orientation) + y * math.cos(orientation)
        rotated_corners.append((x_rotated, y_rotated))
    
    # Convert to UTM coordinates based on the image's position and orientation
    utm_corners = []
    for x, y in rotated_corners:
        # Apply scale and offset based on the image's position
        utm_x = utm['easting'] + x * scale
        utm_y = utm['northing'] + y * scale
        utm_corners.append((utm_x, utm_y))
    

    return Map_Element(utm, utm_corners, orientation, path, width, creation_timestamp, image["id"])


def calculate_px_coords(map_elements, target_map_resolution):
    all_corners = []
    for element in map_elements:
        all_corners.extend(element.utm_corners)
    eastings, northings = zip(*all_corners)
    
    min_easting = min(eastings)
    max_easting = max(eastings)
    min_northing = min(northings)
    max_northing = max(northings)

    total_width = max_easting - min_easting
    total_height = max_northing - min_northing

    scale = target_map_resolution / max(total_width, total_height)

    total_width = int(total_width * scale + 10)
    total_height = int(total_height * scale + 10)


    for element in map_elements:
        element.px_corners = [
            (
                int((corner[0] - min_easting) * scale),
                int((corner[1] - min_northing) * scale)
            ) for corner in element.utm_corners
        ]
        element.px_center = (
            (element.utm['easting'] - min_easting) * scale,
            (element.utm['northing'] - min_northing) * scale
        )
        #calculate the unrotated width of the image in px with the pythagorean theorem of the top corners
        cordern_top_left = element.px_corners[0]
        cordern_top_right = element.px_corners[3]
        width = math.sqrt((cordern_top_right[0] - cordern_top_left[0])**2 + (cordern_top_right[1] - cordern_top_left[1])**2)
        element.scale = width / element.image_width
        
        # invert all heights in y direction, as the y axis is inverted in the image (0,0) is the top left corner
        element.px_corners = [(x, total_height-y) for x, y in element.px_corners]
        element.px_center = (element.px_center[0], total_height-element.px_center[1])

    return (total_width, total_height)


def calc_voronoi_mask(map_elements: list[Map_Element], map_width: int, map_height: int, performance_factor: int = 8, debug_save_path = None):
    fact = 1/performance_factor
    scaled_width = int(map_width * fact)
    scaled_height = int(map_height * fact)

    scaled_centers_x = list()
    scaled_centers_y = list()
    for element in map_elements:
        if element.px_center:
            scaled_centers_x.append(element.px_center[0] * fact)
            scaled_centers_y.append(element.px_center[1] * fact)

    scaled_centers_x = np.array(scaled_centers_x)
    scaled_centers_y = np.array(scaled_centers_y)

    x, y = np.meshgrid(np.arange(0, scaled_width), np.arange(0, scaled_height))
    squared_dist = (x[:, :, np.newaxis] - scaled_centers_x[np.newaxis, np.newaxis, :]) ** 2 + \
                    (y[:, :, np.newaxis] - scaled_centers_y[np.newaxis, np.newaxis, :]) ** 2

        # Find closest center to each pixel location
    indices = np.argmin(squared_dist, axis=2) 

    if debug_save_path:
        draw_and_save_voronoi_mask(indices, debug_save_path)

    logger.info(f"Shape of Voronoi mask: {indices.shape}")
    mask = cv2.resize(indices, (map_width, map_height), interpolation=cv2.INTER_NEAREST)
    logger.info(f"Shape of resized Voronoi mask: {mask.shape}")

    return mask

def _calculate_utm_grid_north_diverence(utm_zone, lat, long):
        #γ = arctan [tan (λ - λ0) × sin φ]
        # where
        # γ is grid convergence,
        # λ0 is longitude of UTM zone's central meridian,
        # φ, λ are latitude, longitude of point in question
        zone_center_longitude = (utm_zone - 1) * 6 - 180 + 3
        gamma = math.atan(math.tan(math.radians(long - zone_center_longitude)) * math.sin(math.radians(lat)))

        return gamma

def draw_and_save_voronoi_mask(voronoi_mask, file_path):
    """
    creates an image in the size of the voronoi mask ,but gives each pixel a tuple color based on the index from the voronoi mask.
    
    Args:
        voronoi_mask (np.ndarray): The Voronoi mask to be drawn.
        file_path (str): The path where the mask image will be saved.
    """
    image = np.zeros((voronoi_mask.shape[0], voronoi_mask.shape[1], 3), dtype=np.uint8)
    unique_indices = np.unique(voronoi_mask)
    hues = [int((i * (360 / len(unique_indices))) * 255/360) for i in range(len(unique_indices))]
    #shuffle the hues to get random colors
    np.random.shuffle(hues)
    colors = np.array([cv2.cvtColor(np.uint8([[[hue, 255, 255]]]), cv2.COLOR_HSV2BGR)[0][0] for hue in hues], dtype=np.uint8)
    
    #fill the image with colors based on the voronoi mask indices
    for i in range(voronoi_mask.shape[0]):
        for j in range(voronoi_mask.shape[1]):
            index = voronoi_mask[i, j]
            if index < len(colors):
                image[i, j] = colors[index]

    #resize the image to the original size with factor 8
    logger.info(f"Saving Voronoi mask with dimensions {image.shape} to {file_path}")


    # Save the image
    save_map_image(image, file_path)

def draw_map(map_elements, voronoi_mask, map_width, map_height, progress_updater):
    map_img = np.zeros((map_height, map_width, 4), dtype=np.uint8)

    batch_size = 32

    map_elements_batches = [map_elements[i:i + batch_size] for i in range(0, len(map_elements), batch_size)]
    logger.info(f"Processing {len(map_elements)} map elements in {len(map_elements_batches)} batches")

    for i, batch in enumerate(map_elements_batches):
        MAX_RETRIES = 3
        
        # with Pool(processes=8) as pool:
        #     map_elements_with_images = pool.map(load_and_transform_images, batch)
        
        logger.info(f"Starting batch {i + 1}/{len(map_elements_batches)}")
        for attempt in range(MAX_RETRIES):
            with Pool(processes=8) as pool:
                try:
                    map_elements_with_images = process_batch_with_timeouts(pool, batch)
                    break  # success
                except Exception as e:
                    logger.error(f"Unexpected failure in batch {i + 1} attempt {attempt + 1}: {e}")
                    pool.terminate()
                    pool.join()
            if attempt == MAX_RETRIES - 1:
                logger.error(f"Batch {i + 1} failed after {MAX_RETRIES} attempts")
                raise TimeoutError("Giving up on this batch")
        logger.info(f"Completed loading batch {i + 1}")
        progress_updater.update_progress_of_map("processing", 50 + (i+1 / len(map_elements_batches)*40))


        for element in map_elements_with_images:
            x1, y1, x2, y2 = element.get_bounds()
            index = element.index
            #crop element image matrix to the bounds
            image = element.image_matrix[:y2 - y1, :x2 - x1]
            voronoi_roi = voronoi_mask[y1:y2, x1:x2]
            #repeat voronoi index, as often, as the dimensions of the image (for example a pixel with one, three or 4 values)
            voronoi_roi = np.repeat(voronoi_roi[:, :, np.newaxis], image.shape[2], axis=2)

            # logger.info(f"shape of map at roi: {map_img[y1:y2, x1:x2].shape}, shape of voronoi_roi: {voronoi_roi.shape}, shape of image: {image.shape}, index: {index}")

            #inside of roi, check voronoi mask index, if index matches, copy pixel data
            merged_roi = np.where(voronoi_roi == index, image, map_img[y1:y2, x1:x2])
            map_img[y1:y2, x1:x2] = merged_roi
            element.clear_image_matrix()  # Clear the image matrix to free memory
        progress_updater.update_progress_of_map("processing", 50 + (i+1 / len(map_elements_batches)*45))


    return map_img

def process_batch_with_timeouts(pool, batch, timeout_per_item=5):
    results = []
    async_results = []

    for element in batch:
        res = pool.apply_async(load_and_transform_images, args=(element,))
        async_results.append(res)

    for i, res in enumerate(async_results):
        try:
            result = res.get(timeout=timeout_per_item)
            results.append(result)
        except TimeoutError:
            logger.warning(f"Timeout processing element {i} in batch")
            results.append(batch[i])  # optionally mark as failed
        except Exception as e:
            logger.error(f"Error processing element {i} in batch: {e}")
            results.append(batch[i])
    return results

def load_and_transform_images(element: Map_Element) -> Map_Element:
    image = cv2.imread(element.image_path, cv2.IMREAD_UNCHANGED)
    if image is None:
        logger.error(f"Failed to load image at {element.image_path}")
        return element
    

    # Resize the image to the target size
    target_size = (int(image.shape[1] * element.scale), int(image.shape[0] * element.scale))
    image = cv2.resize(image, target_size, interpolation=cv2.INTER_LINEAR)

    #add alpha channel if not present
    if image.shape[2] == 3:
        image = cv2.cvtColor(image, cv2.COLOR_BGR2BGRA)

    # Store the transformed image matrix in the element
    image = imutils.rotate_bound(image, -1*math.degrees(element.rotation))

    #scale again to make sure the pixel corners are correct
    width, height = element.get_dims()
    element.image_matrix = cv2.resize(image, (width, height), interpolation=cv2.INTER_LINEAR)
    # Calculate pixel corners based on the scale and position
    return element

def draw_test_map(map_elements, map_width, map_height):
    # Generate a transparent array and fill it with another color for each map element, in the area between the px corners
    test_map = np.zeros((map_height, map_width, 4), dtype=np.uint8)

    for i, element in enumerate(map_elements):
        hue = int((i * (360 / len(map_elements))) * 255/360)
        color = cv2.cvtColor(np.uint8([[[hue, 255, 255]]]), cv2.COLOR_HSV2BGR)[0][0].tolist() + [100]
        cv2.fillPoly(test_map, [np.array(element.px_corners, dtype=np.int32)], color)

    return test_map

def save_map_image(map_img, file_path):
    # Ensure the directory exists
    file_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Save the map image
    cv2.imwrite(str(file_path), map_img)
    logger.info(f"Map image saved to {file_path}")


def _find_map_bounds(map_elements: list[Map_Element]) -> tuple:
    """
    Finds the bounding box of all map elements.
    
    Args:
        map_elements (list[Map_Element]): List of map elements.
    
    Returns:
        tuple: (min_x, min_y, max_x, max_y) coordinates of the bounding box.
    """
    if not map_elements:
        return (0, 0, 0, 0)

    all_corners = []
    for element in map_elements:
        all_corners.extend(element.utm_corners)

    eastings, northings = zip(*all_corners)
    
    min_easting = min(eastings)
    max_easting = max(eastings)
    min_northing = min(northings)
    max_northing = max(northings)

    #convert all four corner individual utm coordinates to lat lon, corner northwest, northeast, southeast, southwest
    corner_nw = (min_easting, max_northing)
    corner_ne = (max_easting, max_northing)
    corner_se = (max_easting, min_northing)
    corner_sw = (min_easting, min_northing)

    corners_utm = [corner_nw, corner_ne, corner_se, corner_sw]
    corners_gps = []

    for corner in corners_utm:
        gps_lon, gps_lat = _utm_to_lat_lon(corner[0], corner[1], element.utm['zone'], element.utm['hemisphere'])
        corners_gps.append((gps_lon, gps_lat))

    min_corner_lat_lon = _utm_to_lat_lon(min_easting, min_northing, element.utm['zone'], element.utm['hemisphere'])
    max_corner_lat_lon = _utm_to_lat_lon(max_easting, max_northing, element.utm['zone'], element.utm['hemisphere'])

    bounds = {
        "gps": {
            "latitude_min": min_corner_lat_lon[1],
            "latitude_max": max_corner_lat_lon[1],
            "longitude_min": min_corner_lat_lon[0],
            "longitude_max": max_corner_lat_lon[0],
        },
        "utm": {
            "northing_min": min_northing,
            "northing_max": max_northing,
            "easting_min": min_easting,
            "easting_max": max_easting,
            "zone": element.utm['zone'],
            "hemisphere": element.utm['hemisphere']
        },
        "corners": {
            "utm": corners_utm,
            "gps": corners_gps
        }
    }
    return bounds

def rotate_to_north(map: np.ndarray, bounds: dict) -> np.ndarray:
    # get the grid north divergence at the center of the map
    center_lat = (bounds['gps']['latitude_min'] + bounds['gps']['latitude_max']) / 2
    center_lon = (bounds['gps']['longitude_min'] + bounds['gps']['longitude_max']) / 2
    utm_zone = bounds['utm']['zone']
    north_divergence = _calculate_utm_grid_north_diverence(utm_zone, center_lat, center_lon)
    # rotate the map to north
    logger.info(f"Rotating map to north with a divergence of {math.degrees(north_divergence)} degrees")
    rotation_angle =  -1* math.degrees(north_divergence)
    rotated_map = imutils.rotate_bound(map, rotation_angle)
    return rotated_map





def _utm_to_lat_lon(easting: float, northing: float, zone: int, hemisphere: str) -> tuple:
    """
    Converts UTM coordinates to latitude and longitude.
  
    Returns:
        tuple: (latitude, longitude).
    """
    import pyproj
    wgs84_crs = "EPSG:4326"
    utm_crs = f"EPSG:326{zone:02d}" if hemisphere == "N" else f"EPSG:327{zone:02d}"
    transformer = pyproj.Transformer.from_crs(utm_crs, wgs84_crs, always_xy=True)
    return transformer.transform(easting, northing)
