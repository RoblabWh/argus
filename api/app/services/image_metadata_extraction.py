import os
import json
import pyproj
import pyexifinfo as p
import re
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)


def _read_metadata(image_path: str) -> dict:
    data = p.get_json(image_path)
    if not data:
        raise ValueError("No metadata found in the image file.")

    strings = json.dumps(data, sort_keys=True, indent=4, separators=(",", ": "))
    python_dict = json.loads(strings)[0]

    #print(f"Metadata for {image_path}:\n{strings}", flush=True)

    return python_dict



def _get_keys(model_name: str) -> dict:
    # load data from json file
    with open("app/cameramodels.json", "r") as file:
        all_keys = json.load(file)
        keys = all_keys.get(model_name, {})
        if keys == {}:
            #print(f"No keys found for {model_name}, falling back to default.", flush=True)
            keys = all_keys.get("default", {})
    return keys


def extract_image_metadata(image_path: str) -> dict:
    metadata = _read_metadata(image_path)
    model_name = metadata.get("EXIF:Model", "Unknown Camera")
    datakeys = _get_keys(model_name)

    #print(f"keys for {model_name}: {datakeys}", flush=True)



    creation_date = _extract_creation_date(metadata, datakeys)
    width, height = _extract_dimensions(metadata, datakeys)
    coord = _extract_coordinates(metadata, datakeys)


    data = {
        "created_at": creation_date,
        "width": width,
        "height": height,
        "camera_model": model_name,
        "coord": coord,
        "panoramic": _check_panoramic(metadata, datakeys),
        "thermal": False,  # will be set later
        "mappable": False,  # will be set later
    }
    logger.debug(f"extracted data for {model_name}: {data}")
    
    data["thermal"] = _check_thermal(
        metadata, datakeys, data, os.path.basename(image_path)
    )
    logger.debug(f"Image thermal check for {model_name}: {data['thermal']}")

    try:
        mappable, mapping_data = _extract_mapping_data(metadata, datakeys, data)
        if mapping_data:
            data["mappable"] = mappable
            data["mapping_data"] = mapping_data
    except Exception as e:
        logger.warning(f"Error extracting mapping data: {e}")
        mapping_data = None
    
    logger.debug(f"Image mappable check for {model_name}: {data['mappable']}")

    # check if some values need adjustment
    if datakeys.get("adjust_data", False):
        data = _adjust_data(model_name, data)
    logger.debug(f"adjusted data for {model_name}: {data}")
    logger.debug(f"final data for {model_name}: {data}")

    return data



def _extract_creation_date(metadata: dict, datakeys: dict) -> str:
    creation_date = metadata.get(datakeys["created_at"], None)
    if creation_date is None:
        return datetime.now(timezone.utc).isoformat()
    elif isinstance(creation_date, str):
        try:
            return datetime.fromisoformat(creation_date)
        except ValueError:
            # If the date is not in ISO format, we can try to parse it
            return datetime.strptime(creation_date, "%Y:%m:%d %H:%M:%S")

    return None

def _extract_dimensions(metadata: dict, datakeys: dict) -> tuple:
    width = metadata.get(datakeys["width"], None)
    height = metadata.get(datakeys["height"], None)

    if width is None or height is None:
        raise ValueError("Width or height metadata is missing in the image file.")

    if isinstance(width, str):
        try:
            width = int(width)
        except ValueError:
            raise ValueError("Width metadata is not a valid integer.")

    if isinstance(height, str):
        try:
            height = int(height)
        except ValueError:
            raise ValueError("Height metadata is not a valid integer.")

    return width, height

def _extract_coordinates(metadata: dict, datakeys: dict) -> dict:
    gps_lat = metadata.get(datakeys["gps"]["lat"], None)
    gps_lon = metadata.get(datakeys["gps"]["lon"], None)
    gps_alt = metadata.get(datakeys["gps"]["alt"], None)
    gps_rel_alt = metadata.get(datakeys["gps"]["rel_alt"], None)
    if gps_lat is None or gps_lon is None:
        coord = None
    else:
        coord = _convert_coord(gps_lat, gps_lon, gps_alt, gps_rel_alt)

    return coord


# def extract_mapping_metadata(image_path: str) -> dict:
#     metadata = _read_metadata(image_path)
#     model_name = metadata.get("EXIF:Model", "Unknown Camera")
#     datakeys = _get_keys(model_name)
#     data_selection = select_mapping_data(metadata, datakeys)
#     if datakeys.adjust_data:
#         data_selection = adjust_data(model_name, data_selection)

#     return data_selection


# def select_mapping_data(metadata: dict, datakeys: dict) -> dict:
#     pass


def _check_mappable(data: dict) -> bool:
    # TODO add  check for orientation data
    if data["coord"]is not None:
        if data["coord"].get("rel_alt", None) is not None and data["coord"].get("utm", None) is not None:
            if data["coord"]["rel_alt"] > 0:
                return True
    else:
        return False


def _check_panoramic(metadata: dict, datakeys: dict) -> bool:
    if "projection_type" not in datakeys:
        return False
    projection_type = metadata.get(datakeys["projection_type"], None)
    if projection_type:
        if projection_type.lower() in ["equirectangular", "spherical"]:
            return True
    return False


def _check_thermal(metadata: dict, datakeys: dict, data: dict, filename: str) -> bool:
    if "ir" not in datakeys:
        return False
    if "ir_value" in datakeys['ir']:
        logger.info(f"Checking if image {filename} is thermal based on ir_value")
        image_source = metadata.get(datakeys["ir"]["ir"], None)
        logger.info(f"Image source: {image_source}")
        if image_source:
            if image_source.lower() == datakeys["ir"]["ir_value"].lower():
                return True
    elif datakeys["ir"].get("ir_image_width", 0) == data["width"] \
        and datakeys["ir"].get("ir_image_height", 0) == data["height"]:
        return True
    elif re.search(datakeys["ir"]["ir_filename_pattern"], filename) is not None:
        return True
    return False


def _normalize_angle(angle: float) -> float:
    """Normalize angle to [-180, 180] range."""
    angle = angle % 360
    if angle > 180:
        angle -= 360
    return angle


def _adjust_data(model_name: str, data: dict) -> dict:
    match model_name:
        case "DJI Mavic 2 Pro":
            pass  # call function to adjust data for DJI Mavic 2 Pro
        case _:
            pass
    return data


def _convert_coord(lat: str, lon: str, alt: str, rel_alt: str) -> dict:
    lat_decimal = _dms_to_decimal(lat)
    lon_decimal = _dms_to_decimal(lon)

    # if alt is a string convert it to float
    if alt is not None:
        try:
            alt = float(alt)
        except ValueError:
            alt = None

    # if rel alt is a tring convert it to float
    if rel_alt is not None:
        try:
            rel_alt = float(rel_alt)
        except ValueError:
            rel_alt = None

    zone = _calculate_zone(lon_decimal)
    hemisphere = "N" if lat_decimal >= 0 else "S"
    zone_letter = _latitude_to_utm_band_letter(lat_decimal)

    easting, northing, utm_crs = _latlon_to_utm(lon_decimal, lat_decimal, zone)
    return {
        "gps": {
            "lat": lat_decimal,
            "lon": lon_decimal,
        },
        "utm": {
            "zone": zone,
            "hemisphere": hemisphere,
            "zone_letter": zone_letter,
            "easting": easting,
            "northing": northing,
            "crs": utm_crs,
        },
        "alt": alt,
        "rel_alt": rel_alt,  
    }


def _dms_to_decimal(dms_str: str) -> float:
    # Regex to parse the DMS format
    pattern = r"(\d+)\s*deg\s*(\d+)'?\s*([\d.]+)\"?\s*([NSEW])"
    match = re.match(pattern, dms_str.strip())
    if not match:
        raise ValueError(f"Invalid DMS format: {dms_str}")

    degrees, minutes, seconds, direction = match.groups()
    decimal = float(degrees) + float(minutes) / 60 + float(seconds) / 3600
    if direction in ["S", "W"]:
        decimal *= -1
    return decimal


def _latlon_to_utm(long: float, lat: float, zone: int) -> tuple:
    # Define the WGS84 and UTM projections using EPSG codes
    wgs84_crs = "EPSG:4326"
    utm_crs = f"EPSG:326{zone:02d}" if lat >= 0 else f"EPSG:327{zone:02d}"

    # Create a transformer object
    transformer = pyproj.Transformer.from_crs(wgs84_crs, utm_crs)

    # Transform the coordinates
    easting, northing = transformer.transform(lat, long)

    return (easting, northing, utm_crs)


def _calculate_zone(long):
    return int((long + 180) / 6) + 1

def _latitude_to_utm_band_letter(lat: float) -> str:
    bands = "CDEFGHJKLMNPQRSTUVWX"
    if not -80 <= lat <= 84:
        raise ValueError("Latitude out of range for UTM: must be between -80 and 84")
    index = int((lat + 80) // 8)
    return bands[index]


def _extract_mapping_data(metadata: dict, datakeys: dict, data: dict) -> tuple:
    mapping_data = {}
    coord = data["coord"]
    thermal = data["thermal"]

    mapping_data["rel_altitude"] = coord.get("rel_alt", None)
    mapping_data["altitude"] = coord.get("alt", None)

    # if mapping_data["rel_altitude"] is None and mapping_data["altitude"] is None:
    #     return False, None
    # elif mapping_data["rel_altitude"] is None:
    if mapping_data["rel_altitude"] is None:
        #TODO check for google API key and set the method to googleelevationapi or similar
        mapping_data["rel_altitude_method"] = "manual"
    else:
        mapping_data["rel_altitude_method"] = "exif"

    
    fov = metadata.get(datakeys["camera_properties"]["fov"], None)
    if fov is None:
        if thermal:
            fov = _load_fallback('fov', data['camera_model'], thermal)
            print(f"FOV not found in metadata, using fallback value: {fov}", flush=True)
        if fov is None:
            return False, None
        mapping_data["fov"] = fov
    else:
        fov = fov.split()[0]
        try:
            fov = float(fov)
        except ValueError:
            raise ValueError(f"FOV value '{fov}' is not a valid float.")
        mapping_data["fov"] = fov

        if datakeys.get("fov_correction", 1.0) != 1.0:
            mapping_data["fov"] *= datakeys["fov_correction"]

    orientation_keys = datakeys["orientation"]
    for key in ("uav_roll", "uav_yaw", "uav_pitch"):
        value = metadata.get(orientation_keys[key], None)
        if value is None:
            return False, None
        try:
            mapping_data[key] = float(value)
        except (TypeError, ValueError):
            return False, None

    for key in ("cam_roll", "cam_yaw", "cam_pitch"):
        value = metadata.get(orientation_keys[key], None)
        if value is None:
            continue
        try:
            mapping_data[key] = float(value)
        except (TypeError, ValueError):
            continue
    
    for uav_key, cam_key in [("uav_yaw", "cam_yaw"), ("uav_roll", "cam_roll")]:
         if uav_key in mapping_data and cam_key in mapping_data:
            yaw_diff = mapping_data[uav_key] - mapping_data[cam_key]
            if abs(yaw_diff) > 140:
                mapping_data[cam_key] = _normalize_angle(mapping_data[cam_key] + 180)



    return True, mapping_data

def _load_fallback(key: str, model_name: str, thermal: bool) -> float:
    # Load fallback values from a JSON file
    with open("app/fallback_camera_properties.json", "r") as file:
        fallbacks = json.load(file)
        logger.info(f"Fallbacks loaded for {model_name}: {fallbacks.get(model_name, {})}")
    
    if model_name in fallbacks:
        values = fallbacks[model_name].get("thermal" if thermal else "optical", {})
    else:
        return None

    if key in values:
        return values[key]
    else:
        return None
