import requests
import json
from datetime import datetime
from geopy.geocoders import Nominatim
from sqlalchemy.orm import Session

import logging

from app.schemas.report import ProcessingSettings, MappingReportUpdate
from app.schemas.image import ImageOut
from app.schemas.weather import WeatherUpdate, WeatherCreate
from app.config import OPEN_WEATHER_API_KEY
import app.crud.report as crud_report
import app.crud.weather as crud_weather


logger = logging.getLogger(__name__)

# def preprocess_report(images: list[ImageOut], report_id: int, settings: ProcessingSettings, db):
def preprocess_report(images: list[ImageOut], report_id: int, db, update_progress_func: callable = None):
    settings = {
        "default_flight_height": 100.0,
        "keep_weather": False,
        "accepted_gimbal_tilt_deviation": 7.5,  # degrees
    }
    
    if not images or len(images) == 0:
        raise ValueError("No images provided for preprocessing.")

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

    if update_progress_func:
        update_progress_func(report_id, "preprocessing", 10.0, db)

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
    crud_report.update_mapping_report(db, report_id, mapping_report_update)

    if weather_data:
        if weather_id:
            # if weather data already exists, update it
            weather_data = WeatherUpdate(**weather_data)
            crud_weather.update_weather_data(db, weather_id, weather_data)
        else:
            # if no weather data exists, create new one
            weather_data = WeatherCreate(**weather_data)
            weather_data = crud_weather.create_weather_data(db, mapping_report_id, weather_data)


    if update_progress_func:
        update_progress_func(report_id, "preprocessing", 20.0, db)

    panos, rest = _filter_pano_images(images)
    if update_progress_func:
        update_progress_func(report_id, "preprocessing", 30.0, db)


    mapping_images_ir, mapping_images_rgb = _filter_mapping_images(rest, settings)
    if update_progress_func:
        update_progress_func(report_id, "preprocessing", 50.0, db)

    logger.info(f"Found {len(panos)} panoramic images and {len(mapping_images_ir)} IR mapping images, {len(mapping_images_rgb)} RGB mapping images.")

    mapping_jobs = _split_mapping_jobs(mapping_images_rgb) + _split_mapping_jobs(mapping_images_ir)
   

    #return mapping_selections
    logger.info(f"Preprocessing completed for report {report_id}. Found {len(mapping_jobs)} mapping jobs.")
    for job in mapping_jobs:
        logger.info(f"Mapping job type: {job['type']}, images count: {len(job['images'])}")
    if update_progress_func:
        update_progress_func(report_id, "preprocessing", 100.0, db)

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
        print(f"Error extracting location: {e}")
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
    
    if not OPEN_WEATHER_API_KEY:
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
        print(f"Error fetching past weather data: {e}")
     
    try:
        # Fallback to current weather if historical data fails
        weather = _call_open_weather_api(gps)
        useful_data = _extract_useful_weather_data(weather)
        return useful_data
    except Exception as e:
        print(f"Error fetching current weather data: {e}")
        return None


def _call_open_weather_api(gps: dict, timestamp: float = None) -> dict:
    """
    Call the Open Weather API to get weather data for the given GPS coordinates and timestamp.
    """
    if timestamp:
        api_call = f"https://api.openweathermap.org/data/2.5/onecall/timemachine?lat={gps['lat']}&lon={gps['lon']}&dt={str(int(timestamp))}&appid={OPEN_WEATHER_API_KEY}&units=metric"
    else:
        api_call = f"https://api.openweathermap.org/data/2.5/weather?lat={gps['lat']}&lon={gps['lon']}&appid={OPEN_WEATHER_API_KEY}&units=metric"

    results = requests.get(api_call)
    results = results.json()
    print(f"Open Weather API call: {api_call}")
    if results:
        print(f"Open Weather API results: {results}")
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
        average_altitude = 0

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
    if len(images) < 3:
        return []

    # make sure both lists are sorted by created_at
    images.sort(key=lambda x: x.created_at)
    # separate sequences based on time differences
    image_sequences = _separate_sequences(images)
    logger.info(f"Separated {len(image_sequences)} sequences from {len(images)} images.")

    mapping_jobs = []
    for seq in image_sequences:
        if len(seq) > 3:
            type = "ir" if seq[0].thermal == "ir" else "rgb"
            mapping_jobs.append({"type": type, "images": seq})

    return mapping_jobs

def _separate_sequences(images: list[ImageOut]) -> list[list[ImageOut]]:
    """
    Separate images into sequences based on the time difference.
    """
    if not images:
        return []

    delta_times = []
    delta_distances = []
    sequences = []
    current_sequence = [images[0]]

    for i in range(1, len(images)):
        date_a = images[i-1].created_at
        date_b = images[i].created_at
        time_diff = (date_b - date_a).total_seconds()
        delta_times.append(time_diff)

        utm_a = images[i-1].coord.get("utm")
        utm_b = images[i].coord.get("utm")
        if utm_a and utm_b:
            distance = ((utm_b['easting'] - utm_a['easting']) ** 2 + (utm_b['northing'] - utm_a['northing']) ** 2) # root can be ignored for performance if all compared values are squared
            delta_distances.append(distance)
    
    median_time_diff = sorted(delta_times)[len(delta_times) // 2] if delta_times else 0
    median_distance = sorted(delta_distances)[len(delta_distances) // 2] if delta_distances else 0
    logger.info(f"Median time difference: {median_time_diff}, Median distance: {median_distance}")


    for i in range(0, len(images)-1):
        if delta_times[i] > 2 * median_time_diff or delta_distances[i] > 5 * median_distance:
            sequences.append(current_sequence)
            current_sequence = [images[i]]
        else:
            current_sequence.append(images[i])

    if current_sequence:
        sequences.append(current_sequence)

    return sequences