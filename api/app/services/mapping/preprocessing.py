import requests
import json
from datetime import datetime
from geopy.geocoders import Nominatim
from sqlalchemy.orm import Session
from billiard import Pool, Manager
from typing import List

import threading

import logging

from app.config import config

from app.schemas.report import ProcessingSettings, MappingReportUpdate
from app.schemas.image import ImageOut, ThermalDataCreate
from app.schemas.weather import WeatherUpdate, WeatherCreate
import app.crud.report as crud_report
import app.crud.weather as crud_weather
import app.crud.images as crud_image
import app.services.thermal.thermal_processing as thermal_processing
from app.services.mapping.progress_updater import ProgressUpdater

logger = logging.getLogger(__name__)

def preprocess_report(report_id: int, images: list[ImageOut], settings: ProcessingSettings, db, progress_updater: ProgressUpdater):
    settings = settings.dict() if isinstance(settings, ProcessingSettings) else settings
    # crud_image.delete_all_thermal_data(db)  # Clear old thermal data before processing new images
    if not images or len(images) == 0:
        raise ValueError("No images provided for preprocessing.")

    # Step 1 process thermal images (30%)
    images = _process_thermal_images(images, report_id, db, progress_updater)
    progress_updater.update_progress("preprocessing", 33.0)
    


    # Step 2 extract Flight Data (33-50%)
    images.sort(key=lambda x: x.created_at)
    logger.info(f"Preprocessing report {report_id} with {len(images)} images.")
    reference_image = _find_first_image_with_gps(images)
    mapping_report_id = reference_image.mapping_report_id 

    weather_data = crud_weather.get_weather_data_by_mapping_report_id(db, mapping_report_id)
    logger.info(f"Weather data for mapping report {mapping_report_id}: {weather_data}")
    weather_id = None
    if weather_data:
        weather_id = weather_data.id
    else:
        settings["keep_weather"] = False

    coord = None
    address = "Unknown Location"
    weather_data = None
    if reference_image:
        coord = reference_image.coord
        address = _extract_location(reference_image)
        if not settings.get("keep_weather", False):
            weather_data = _get_weather_data(reference_image)
            if weather_data:
                weather_data["mapping_report_id"] = mapping_report_id
    progress_updater.update_progress("preprocessing", 40.0)


    flight_timestamp = images[0].created_at
    flight_duration = _calculate_flight_duration(images)
    images, average_altitude, covered_area = _check_altitude(images, settings)
    uav_models = _get_uav_data(images)

    mapping_report_data = {
        "report_id": report_id,
        "flight_timestamp": flight_timestamp,
        "coord": coord,
        "address": address,
        "flight_duration": flight_duration,
        "flight_height": average_altitude,
        "covered_area": covered_area,
        "uav": uav_models.get("camera_models", ["Unknown"])[0],  # use first camera model as UAV
        "image_count": len(images),
    }
    mapping_report_update = MappingReportUpdate(**mapping_report_data)
    # save extracted data to the database
    updated_report = crud_report.update_mapping_report(db, report_id, mapping_report_update)
    progress_updater.update_progress("preprocessing", 46.0)


    if weather_data:
        if weather_id:
            # if weather data already exists, update it
            weather_data = WeatherUpdate(**weather_data)
            crud_weather.update_weather_data(db, weather_id, weather_data)
        else:
            # if no weather data exists, create new one
            weather_data = WeatherCreate(**weather_data)
            weather_data = crud_weather.create_weather_data(db, mapping_report_id, weather_data)
    progress_updater.update_progress("preprocessing", 55.0)



    # Step 3 extract UAV/ Flight Data (55-70%)
    panos, rest = _filter_pano_images(images)
    progress_updater.update_progress("preprocessing", 66.0)



    # Step 4 filter mapping images and build mapping jobs (70-96%)
    mapping_images_ir, mapping_images_rgb = _filter_mapping_images(rest, settings)
    logger.info(f"Found {len(panos)} panoramic images and {len(mapping_images_ir)} IR mapping images, {len(mapping_images_rgb)} RGB mapping images.")
    progress_updater.update_progress("preprocessing", 80.0)
    

    mapping_jobs = _split_mapping_jobs(mapping_images_rgb) + _split_mapping_jobs(mapping_images_ir)
    mapping_jobs = _set_bounds_and_corners_per_job(mapping_jobs)
    progress_updater.update_progress("preprocessing", 96.0)


    #return mapping_selections
    logger.info(f"Preprocessing completed for report {report_id}. Found {len(mapping_jobs)} mapping jobs.")
    for job in mapping_jobs:
        logger.info(f"Mapping job type: {job['type']}, images count: {len(job['images'])}")
    

    return mapping_jobs

def _find_first_image_with_gps(images: list[ImageOut]) -> ImageOut | None:
    """
    Find the first image with GPS coordinates.
    """
    for image in images:
        if image.coord:
            return image
    return None

def _extract_location(image: ImageOut) -> str:
    """
    Extract the location from the first image's coordinates.
    """
    try:
        geolocator = Nominatim(user_agent="12879379127889378123")
        coord = image.coord['gps']
        location = geolocator.reverse(f"{coord['lat']}, {coord['lon']}")
    except Exception as e:
        logger.error(f"Error extracting location: {e}")
        return "Unknown Location"

    return location.address if location else "Unknown Location"


##########
## WEATHER
##########

def _get_weather_data(image: ImageOut) -> dict:
    """
    Get weather data for the given image.
    This is a placeholder function and should be replaced with actual weather data retrieval logic.
    """
    
    config.refresh()
    if not config.OPEN_WEATHER_API_KEY:
        raise ValueError("Open Weather API key is not set in the configuration.")
    
    gps = image.coord.get('gps')
    timestamp = image.created_at
    #convert timestemp to unix timestamp if it is a datetime object
    if isinstance(timestamp, str):
        timestamp = datetime.fromisoformat(timestamp).timestamp()
    elif isinstance(timestamp, datetime):
        timestamp = timestamp.timestamp()
        
    try:
        weather = _call_open_weather_api(gps, timestamp)
        useful_data = _extract_useful_weather_data(weather, timestamp)
        return useful_data
    except Exception as e:
        logger.warning(f"Error fetching past weather data: {e}")
     
    try:
        # Fallback to current weather if historical data fails
        weather = _call_open_weather_api(gps)
        useful_data = _extract_useful_weather_data(weather)
        return useful_data
    except Exception as e:
        logger.warning(f"Error fetching current weather data: {e}")
        return None


def _call_open_weather_api(gps: dict, timestamp: float = None) -> dict:
    """
    Call the Open Weather API to get weather data for the given GPS coordinates and timestamp.
    """
    if timestamp:
        api_call = f"https://api.openweathermap.org/data/2.5/onecall/timemachine?lat={gps['lat']}&lon={gps['lon']}&dt={str(int(timestamp))}&appid={config.OPEN_WEATHER_API_KEY}&units=metric"
    else:
        api_call = f"https://api.openweathermap.org/data/2.5/weather?lat={gps['lat']}&lon={gps['lon']}&appid={config.OPEN_WEATHER_API_KEY}&units=metric"

    results = requests.get(api_call)
    results = results.json()
    logger.info(f"Open Weather API call: {api_call}")
    if results:
        logger.debug(f"Open Weather API results: {results}")
        if results["cod"] == 401 or results["cod"] == "401":
            raise Exception("API key invalid, falling back to default key")
        if results["cod"] == 400 or results["cod"] == "400":
            raise Exception("Bad request (if returned from historical call timestamp too old or out of range of key)")
        return results
    else:
        raise ValueError("No results returned from Open Weather API.")

def _extract_useful_weather_data(weather: dict, timestamp: float = None) -> dict:

    if timestamp:
        weather = weather.get("hourly", {})[0]
        weather_main = weather
        weather_wind = weather
    else:
        weather_main = weather.get("main", {})
        weather_wind = weather.get("wind", {})
    
    weather_state = weather.get("weather", [{}])[0]

    useful_data = {
        "open_weather_id": str(weather_state.get("id")),
        "description": weather_state.get("description"),
        "temperature": weather_main.get("temp"),
        "humidity": weather_main.get("humidity"),
        "pressure": weather_main.get("pressure"),
        "wind_speed": weather_wind.get("speed"),
        "wind_dir_deg": weather_wind.get("deg"),
        "visibility": weather.get("visibility", "unknown"),
    }

    if timestamp:
        #convert timestamp to YYYY-MM-DD HH:MM:SS format
        timestamp_iso = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
        useful_data["timestamp"] = timestamp_iso
    else:
        timestamp = weather.get("dt")
        if timestamp:
            #convert timestamp to YYYY-MM-DD HH:MM:SS format
            timestamp = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
        else:
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        useful_data["timestamp"] = timestamp

    return useful_data



##################
# UAV/ Flight Data
##################

def _calculate_flight_duration(images: list[ImageOut]) -> str:
    """
    Calculate the flight duration based on the first and last image timestamps.
    """
    if not images:
        return "00:00:00"

    start_time = images[0].created_at
    end_time = images[-1].created_at

    if isinstance(start_time, str):
        start_time = datetime.fromisoformat(start_time)
    if isinstance(end_time, str):
        end_time = datetime.fromisoformat(end_time)

    duration = end_time - start_time
    return duration.total_seconds()


def _get_uav_data(images: list[ImageOut]) -> dict:
    # form every image get camera_model and in the end return every unique camera_model
    camera_models = set()
    for image in images:
        if image.camera_model:
            camera_models.add(image.camera_model)
    return {"camera_models": list(camera_models)}


def _check_altitude(images: list[ImageOut], settings: dict) -> tuple:
    """
    Check the altitude of the images and calculate the average altitude and covered area.
    If no altitude is found, set with preferred setting option.
    """
    altitude_sum = 0.0
    altitude_count = 0
    northhing_max = float('-inf')
    northhing_min = float('inf')
    easting_max = float('-inf')
    easting_min = float('inf')

    default_altitude = settings.get("default_altitude", 100.0)  # Default altitude if none found

    for image in images:
        if image.mapping_data:

            rel_altitude = None
            if image.mapping_data.rel_altitude is not None:
                rel_altitude = image.mapping_data.rel_altitude
            else:
                rel_altitude = default_altitude  # Use default altitude if not set
            altitude_sum += rel_altitude
            altitude_count += 1

            if image.coord:
                utm = image.coord.get("utm")
                northhing_max = max(northhing_max, utm.get("northing", float('-inf')))
                northhing_min = min(northhing_min, utm.get("northing", float('inf')))
                easting_max = max(easting_max, utm.get("easting", float('-inf')))
                easting_min = min(easting_min, utm.get("easting", float('inf')))
            

    if altitude_count > 1:
        average_altitude = altitude_sum / altitude_count
    else:
        average_altitude = altitude_sum if altitude_count == 1 else default_altitude

    covered_area = 0.0
    if northhing_max != float('-inf') and northhing_min != float('inf') and easting_max != float('-inf') and easting_min != float('inf'):
        covered_area = (northhing_max - northhing_min) * (easting_max - easting_min)

    return images, average_altitude, covered_area


def _filter_pano_images(images: list[ImageOut]) -> tuple:
    """
    Filter panoramic images from the list of images.
    """
    panos = []
    rest = []
    for image in images:
        if image.panoramic:
            panos.append(image)
        else:
            rest.append(image)
    return panos, rest

def _filter_mapping_images(images: list[ImageOut], settings: dict) -> list:
    """
    Filter images that are suitable for mapping based on the settings.
    """
    mapping_images_ir, mapping_images_rgb = [], []
    for image in images:
        if not image.mappable or not image.mapping_data:
            continue

        if abs(90+image.mapping_data.cam_pitch) <= settings.get("accepted_gimbal_tilt_deviation", 7.5):
            if image.thermal:
                mapping_images_ir.append(image)
            else:
                mapping_images_rgb.append(image)
    
    return mapping_images_ir, mapping_images_rgb

def _split_mapping_jobs(images: list[ImageOut]) -> list:

    if not images:
        return []
    if len(images) <= 3:
        return []

    # make sure both lists are sorted by created_at
    images.sort(key=lambda x: x.created_at)
    # separate sequences based on time differences
    image_sequences = _separate_sequences(images)
    logger.info(f"Separated {len(image_sequences)} sequences from {len(images)} images.")
    logger.info(f"Sequence lengths: {[len(seq) for seq in image_sequences]}")

    mapping_jobs = []
    for seq in image_sequences:
        if len(seq) >= 4:
            type = "ir" if seq[0].thermal else "rgb"
            mapping_jobs.append({"type": type, "images": seq})
    logger.info(f"Created {len(mapping_jobs)} mapping jobs from {len(image_sequences)} sequences.")
    return mapping_jobs

def _separate_sequences(images: list[ImageOut]) -> list[list[ImageOut]]:
    """
    Separate images into sequences based on the time difference and distance.
    """
    if not images:
        return []

    # Build paired deltas — use sentinel distance when UTM is missing
    deltas = []  # list of (time_diff, distance_squared)
    for i in range(1, len(images)):
        date_a = images[i-1].created_at
        date_b = images[i].created_at
        time_diff = (date_b - date_a).total_seconds()

        utm_a = images[i-1].coord.get("utm") if images[i-1].coord else None
        utm_b = images[i].coord.get("utm") if images[i].coord else None
        if utm_a and utm_b:
            distance = (utm_b['easting'] - utm_a['easting']) ** 2 + (utm_b['northing'] - utm_a['northing']) ** 2
        else:
            distance = 0.0  # no UTM data — don't split on distance

        deltas.append((time_diff, distance))

    delta_times = [d[0] for d in deltas]
    delta_distances = [d[1] for d in deltas]

    median_time_diff = sorted(delta_times)[len(delta_times) // 2] if delta_times else 0
    if median_time_diff <= 3.0:  # if median time difference is very small, use a fixed threshold
        median_time_diff = 3.0
    median_distance = sorted(delta_distances)[len(delta_distances) // 2] if delta_distances else 0
    if median_distance <= 2.0:  # if median distance is very small, use a fixed threshold (5m distance squared)
        median_distance = 2.0
    logger.info(f"Median time difference: {median_time_diff}, Median distance: {median_distance}")

    sequences = []
    current_sequence = [images[0]]

    for i in range(len(deltas)):
        if deltas[i][0] > 10 * median_time_diff or deltas[i][1] > 15 * median_distance:
            sequences.append(current_sequence)
            current_sequence = [images[i + 1]]
        else:
            current_sequence.append(images[i + 1])

    if current_sequence:
        sequences.append(current_sequence)

    return sequences

def _set_bounds_and_corners_per_job(mapping_jobs: list[dict]) -> list[dict]:
    # get the min and max coordinates for each job
    for job in mapping_jobs:
        if not job.get("images"):
            continue

        northing_max = float('-inf')
        northing_min = float('inf')
        easting_max = float('-inf')
        easting_min = float('inf')
        longitude_max = float('-inf')
        longitude_min = float('inf')
        latitude_max = float('-inf')
        latitude_min = float('inf')
        basic_utm = None

        for image in job["images"]:
            if image.coord and image.coord.get("utm"):
                utm = image.coord["utm"]
                gps = image.coord["gps"]
                basic_utm = basic_utm or utm
                northing_max = max(northing_max, utm["northing"])
                northing_min = min(northing_min, utm["northing"])
                easting_max = max(easting_max, utm["easting"])
                easting_min = min(easting_min, utm["easting"])
                longitude_max = max(longitude_max, gps["lon"])
                longitude_min = min(longitude_min, gps["lon"])
                latitude_max = max(latitude_max, gps["lat"])
                latitude_min = min(latitude_min, gps["lat"])

        if basic_utm is None:
            continue

        bounds_coordinates = {
            "utm": {
                "zone": basic_utm["zone"],
                "crs": basic_utm["crs"],
                "hemisphere": basic_utm["hemisphere"],
                "zone_letter": basic_utm["zone_letter"],
                "northing_max": northing_max,
                "northing_min": northing_min,
                "easting_max": easting_max,
                "easting_min": easting_min
            },
            "gps": {
                "longitude_max": longitude_max,
                "longitude_min": longitude_min,
                "latitude_max": latitude_max,
                "latitude_min": latitude_min
            }
        }

        corner_coordinates = {
            "top_left": {"northing": northing_max, "easting": easting_min},
            "top_right": {"northing": northing_max, "easting": easting_max},
            "bottom_left": {"northing": northing_min, "easting": easting_min},
            "bottom_right": {"northing": northing_min, "easting": easting_max}
        }

        job["bounds"] = bounds_coordinates
        job["corners"] = corner_coordinates

    return mapping_jobs



def process_thermal_wrapper(data, progress_queue):
    from pathlib import Path

    path = Path(data["target_path"])
    if path.exists():
        thermal_matrix = thermal_processing.load_temperature_matrix(path)
        min_temp, max_temp = thermal_processing.get_temperature_range(thermal_matrix)
    else:
        try:
            min_temp, max_temp = thermal_processing.process_thermal_image(data["url"], path)
        except Exception as e:
            logger.error(f"Error processing thermal image {data['image_id']}: {e}")
            progress_queue.put(1)
            return {
                "image_id": data["image_id"],
                "counterpart_id": data["counterpart_id"],
                "counterpart_scale": data["counterpart_scale"],
                "min_temp": None,
                "max_temp": None,
                "temp_matrix_path": None
            }

    # Report progress
    progress_queue.put(1)

    return {
        "image_id": data["image_id"],
        "counterpart_id": data["counterpart_id"],
        "counterpart_scale": data["counterpart_scale"],
        "min_temp": min_temp,
        "max_temp": max_temp,
        "temp_matrix_path": str(path)
    }


def progress_listener(queue, updater, total):
    completed = 0
    while completed < total:
        try:
            _ = queue.get(timeout=1)
            completed += 1
            if completed % 5 == 0 or completed == total:
                updater.update_partial_progress("preprocessing", 10.0, 30.0, total, completed)
        except:
            pass


def _process_thermal_images(images: List[ImageOut], report_id: int, db: Session, progress_updater):
    images.sort(key=lambda x: x.created_at)
    thermal_images = [img for img in images if img.thermal]
    rgb_images = [img for img in images if not img.thermal]

    with open("app/cameramodels.json", "r") as file:
        camera_specific_keys = json.load(file)

    total_ir_images = len(thermal_images)
    thermal_metadata_list = []

    if total_ir_images == 0:
        logger.info("No thermal images found, skipping thermal processing.")
        return images
    
    rgb_start = 0  # index pointer into rgb_images — avoids O(n²) list slicing
    matched_rgb = set()  # track matched RGB indices to avoid reuse

    for thermal_image in thermal_images:
        closest_rgb_image_index = -1
        smallest_diff = float("inf")
        counterpart = None
        discard_to_index = -1

        for i in range(rgb_start, len(rgb_images)):
            if i in matched_rgb:
                continue
            rgb_image = rgb_images[i]
            time_diff = (rgb_image.created_at - thermal_image.created_at).total_seconds()
            if time_diff > 2:  # rgb too far ahead, rest will be further (sorted)
                break
            if time_diff < -2:  # rgb too far behind
                discard_to_index = i
                continue
            if abs(time_diff) < smallest_diff:
                smallest_diff = abs(time_diff)
                closest_rgb_image_index = i
            elif abs(time_diff) > smallest_diff:  # past the best match, stop
                break

        if closest_rgb_image_index != -1:
            rgb_start = closest_rgb_image_index  # advance pointer past old entries
            matched_rgb.add(closest_rgb_image_index)
            counterpart = rgb_images[closest_rgb_image_index]
        elif discard_to_index != -1:
            rgb_start = discard_to_index  # advance pointer past too-old entries

        camera_model = thermal_image.camera_model
        scale = camera_specific_keys.get(camera_model, {}).get("ir", {}).get("ir_scale") or \
                camera_specific_keys.get("default", {}).get("ir", {}).get("ir_scale", 0.4)

        target_path = config.UPLOAD_DIR / str(report_id) / "thermal" / f"{thermal_image.id}.npy"

        thermal_metadata_list.append({
            "url": thermal_image.url,
            "target_path": str(target_path),
            "image_id": thermal_image.id,
            "counterpart_id": counterpart.id if counterpart else None,
            "counterpart_scale": scale
        })

        if len(thermal_metadata_list) % 10 == 0:
            progress_updater.update_partial_progress("preprocessing", 5.0, 10.0, total_ir_images, len(thermal_metadata_list))

    # -- PARALLEL PROCESSING --
    manager = Manager()
    progress_queue = manager.Queue()

    progress_thread = threading.Thread(
        target=progress_listener,
        args=(progress_queue, progress_updater, len(thermal_metadata_list)),
    )
    progress_thread.start()

    with Pool(processes=6) as pool:
        results = pool.starmap(
            process_thermal_wrapper,
            [(data, progress_queue) for data in thermal_metadata_list]
        )

    progress_thread.join()

    # -- INSERT TO DB --
    thermal_data_list = [
        ThermalDataCreate(
            image_id=item["image_id"],
            counterpart_id=item["counterpart_id"],
            counterpart_scale=item["counterpart_scale"],
            min_temp=item["min_temp"],
            max_temp=item["max_temp"],
            temp_matrix_path=item["temp_matrix_path"],
            temp_embedded=True,
            lut_name="white_hot"
        )
        for item in results
    ]

    crud_image.create_multiple_thermal_data(db, thermal_data_list)

    for img in images:
        if img.thermal:
            db.refresh(img, ["thermal_data"])
    return images

