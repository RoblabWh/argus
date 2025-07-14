import os
import math
import cv2
import imutils
import numpy as np
from app.config import UPLOAD_DIR
from app.schemas.image import ImageOut, MappingDataOut
import logging

import billiard as multiprocessing
from billiard import Pool

logger = logging.getLogger(__name__)

class Map_Element:
    def __init__(self, utm, utm_corners, rotation, image_path, image_width, creation_timestamp):
        """
        Initializes a Map_Element with the given parameters.
        """
        self.utm = utm
        self.utm_corners = utm_corners
        self.rotation = rotation
        self.image_path = image_path
        self.image_width = image_width
        self.creation_timestamp = creation_timestamp
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



 
def map_images(report_id: int, mapping_selection: dict, db, update_progress_func=None, total_maps=1, map_index=0):
    """
    Maps images based on the provided mapping selection.
    
    Args:
        report_id (int): The ID of the report being processed.
        mapping_selection (dict): The mapping selection containing image data and metadata.
        db (Session): Database session dependency.
        update_progress_func (callable, optional): Function to update progress. Defaults to None.
        total_maps (int, optional): Total number of maps to process. Defaults to 1.
        map_index (int, optional): Index of the current map being processed. Defaults to 0.
    """
    # Simulate image mapping logic
    logger.info(f"Mapping images for report {report_id} with selection {mapping_selection}")
    start_progress = 0.0 if map_index == 0 else 100.0 * map_index / total_maps

    settings = {
        "default_flight_height": 100.0,
        "keep_weather": False,
        "accepted_gimbal_tilt_deviation": 7.5,  # degrees
        "target_image_size": 6144,  # px
    }

    # generate a map element for very image in mapping_selection 
    # calculate the utm corners of the image based on the mapping selection in parallel using multiprocessing pool
    # with Pool(processes=int(os.cpu_count()/2)) as pool:
    dicts = []
    for image in mapping_selection['images']:
        if image.mapping_data:
            mapping_data_out = MappingDataOut.from_orm(image.mapping_data)
        else:
            mapping_data_out = None

        image_dict = ImageOut.from_orm(image).dict()
        image_dict["mapping_data"] = mapping_data_out.dict() if mapping_data_out else None
        dicts.append(image_dict)

    reference_yaw = calculate_reference_yaw(mapping_selection['images'])
    params = [(image, reference_yaw) for image in dicts]

    with Pool(processes=8) as pool:
        map_elements = pool.starmap(calculate_utm_corners, params)

    for i, element in enumerate(map_elements):
        element.index = i

    if update_progress_func:
        progress = (20.0 / total_maps) + start_progress
        update_progress_func(report_id, "processing", progress, db)

    map_width, map_height = calculate_px_coords(map_elements, settings['target_image_size'])

    if update_progress_func:
        progress = (40.0 / total_maps) + start_progress
        update_progress_func(report_id, "processing", progress, db)

    # The map elements should contain the utm corners and px corners of each image based on the orientation, position, pov and image size
    # based on the map elements, a mask layer similar to a voronoi texture is created

    map_img = draw_test_map(map_elements, map_width, map_height)
    file_path = UPLOAD_DIR / str(report_id) / f"map_{map_index}.png"
    save_map_image(map_img, file_path)
    logger.info(f"Map image for report {report_id} saved as {file_path}")

    voronoi = calc_voronoi_mask(map_elements, map_width, map_height, performance_factor=8)

    map = draw_map(map_elements, voronoi, map_width, map_height)
    file_path = UPLOAD_DIR / str(report_id) / f"final_map_{map_index}.png"
    save_map_image(map, file_path)

    # file_path = UPLOAD_DIR / str(report_id) / f"voronoi_{map_index}.png"
    # draw_and_save_voronoi_mask(voronoi, file_path)

    # the images get loaded in batches, transformed according to the map elements and added to the final map image
    # The final map image is saved to the filesystem and metadata is stored in the database 

    # Update progress if a function is provided
    if update_progress_func:
        progress = (100.0 / total_maps) + start_progress
        update_progress_func(report_id, "processing", progress, db)


def calculate_reference_yaw(images: list[ImageOut]) -> float:
    margin_orientation_degrees = 1.5
    margin_trajectory_degrees = 5

    images_len = len(images)
    if images_len > 3:
        dumb_offset = calc_dumb_offset(images[0]) #uav yaw - cam yaw
        return dumb_offset


    for i in range(len(images)-2):
        roi = images[i:i+3]

        time_deltas = images[i+1].created_at - images[i].created_at, images[i+2].created_at - images[i+1].created_at
        logger.info(f"time deltas: {time_deltas}")

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

        v_diff_a = np.array((northing2, easting2)) - np.array((northing1, easting1))
        v_diff_b = np.array((northing3, easting3)) - np.array((northing2, easting2))
        angle = np.arccos(np.dot(v_diff_a, v_diff_b) / (np.linalg.norm(v_diff_a) * np.linalg.norm(v_diff_b)))
        angle = np.degrees(angle)
        if angle < margin_trajectory_degrees:
            print("reference yaw is calculated by using images: ", i, i+1, i+2, flush=True)
            reference_yaw = np.arctan2(v_diff_b[0], v_diff_b[1])
            reference_yaw = np.degrees(reference_yaw)
            reference_yaw = reference_yaw - roi[1].mapping_data.cam_yaw
            print("REFERENCE YAW", reference_yaw, flush=True)
            return float(reference_yaw)
    return calc_dumb_offset(images[0])


def calc_dumb_offset(image: ImageOut) -> float:
    if not image.mapping_data or not image.mapping_data.cam_yaw:
        return 0.0
    return image.mapping_data.uav_yaw - image.mapping_data.cam_yaw



def calculate_utm_corners(image: ImageOut, reference_yaw: float) -> Map_Element:
    fov = image["mapping_data"]["fov"]
    rel_altitude = image["mapping_data"]["rel_altitude"]
    uav_yaw = -1 * math.radians(image["mapping_data"]["uav_yaw"]) 
    cam_yaw = -1 * (math.radians(image["mapping_data"]["cam_yaw"]) + math.radians(reference_yaw))
    width = image["width"]
    height = image["height"]
    utm = image["coord"]["utm"]
    path = image["url"]
    creation_timestamp = image["created_at"]

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
        x_rotated = x * math.cos(cam_yaw) - y * math.sin(cam_yaw)
        y_rotated = x * math.sin(cam_yaw) + y * math.cos(cam_yaw)
        rotated_corners.append((x_rotated, y_rotated))
    
    # Convert to UTM coordinates based on the image's position and orientation
    utm_corners = []
    for x, y in rotated_corners:
        # Apply scale and offset based on the image's position
        utm_x = utm['easting'] + x * scale
        utm_y = utm['northing'] + y * scale
        utm_corners.append((utm_x, utm_y))
    

    return Map_Element(utm, utm_corners, cam_yaw, path, width, creation_timestamp)


def calculate_px_coords(map_elements, target_image_size):
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

    scale = target_image_size / max(total_width, total_height)

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


def calc_voronoi_mask(map_elements: list[Map_Element], map_width: int, map_height: int, performance_factor: int = 8):
    """
    Generates a Voronoi mask based on the pixel corners of the map elements.
    
    Args:
        map_elements (list): List of Map_Element objects containing pixel corners.
        map_width (int): Width of the map image.
        map_height (int): Height of the map image.
    
    Returns:
        np.ndarray: A mask image with the Voronoi texture applied.
    """
    fact = 1/performance_factor
    mask = np.zeros((int(map_height*fact), int(map_width*fact), 1), dtype=np.uint8)

    scaled_centers = []
    for element in map_elements:
        if element.px_center:
            scaled_centers.append((element.px_center[0] * fact, element.px_center[1] * fact))

    for y in range(int(map_height*fact)):
        for x in range(int(map_width*fact)):
            min_dist = float('inf')
            closest_element_index = None

            for i, center in enumerate(scaled_centers):
                # Calculate the distance from the pixel to the center of the map element
                dist = (x - center[0])**2 + (y - center[1])**2
                if dist < min_dist:
                    min_dist = dist
                    closest_element_index = i

            # Assign color based on the closest map element
            if closest_element_index is not None:
                mask[y, x] = closest_element_index

    # Resize the mask to the original map size
    mask = cv2.resize(mask, (map_width, map_height), interpolation=cv2.INTER_NEAREST)

    return mask

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
    colors = np.array([cv2.cvtColor(np.uint8([[[hue, 255, 255]]]), cv2.COLOR_HSV2BGR)[0][0] for hue in hues], dtype=np.uint8)
    
    #fill the image with colors based on the voronoi mask indices
    for i in range(voronoi_mask.shape[0]):
        for j in range(voronoi_mask.shape[1]):
            index = voronoi_mask[i, j]
            if index < len(colors):
                image[i, j] = colors[index]

    #resize the image to the original size with factor 8
    image = cv2.resize(image, (voronoi_mask.shape[1] * 8, voronoi_mask.shape[0] * 8), interpolation=cv2.INTER_NEAREST)


    # Save the image
    save_map_image(image, file_path)

def draw_map(map_elements, voronoi_mask, map_width, map_height):
    """
    Draws the map elements on a blank image and applies the Voronoi mask.
    
    Args:
        map_elements (list): List of Map_Element objects containing pixel corners.
        voronoi_mask (np.ndarray): The Voronoi mask to be applied.
        map_width (int): Width of the map image.
        map_height (int): Height of the map image.
    
    Returns:
        np.ndarray: The final map image with elements drawn and Voronoi mask applied.
    """
    # Create a blank image with transparency
    map_img = np.zeros((map_height, map_width, 4), dtype=np.uint8)

    batch_size = 32

    map_elements_batches = [map_elements[i:i + batch_size] for i in range(0, len(map_elements), batch_size)]
    logger.info(f"Processing {len(map_elements)} map elements in {len(map_elements_batches)} batches")
    for batch in map_elements_batches:
        with Pool(processes=8) as pool:
            map_elements_with_images = pool.map(load_and_transform_images, batch)

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

    return map_img

def load_and_transform_images(element: Map_Element) -> Map_Element:
    """
    Loads the image for a map element, applies transformations, and calculates pixel corners.
    
    Args:
        element (Map_Element): The map element containing image path and metadata.
    
    Returns:
        Map_Element: The updated map element with pixel corners and transformed image.
    """
    # Load the image
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

