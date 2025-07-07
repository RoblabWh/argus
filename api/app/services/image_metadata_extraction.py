import os
import json
import pyproj
import pyexifinfo as p
import re
from datetime import datetime, timezone


def read_metadata(image_path: str) -> dict:
    data = p.get_json(image_path)
    if not data:
        raise ValueError("No metadata found in the image file.")

    strings = json.dumps(data, sort_keys=True, indent=4, separators=(",", ": "))
    python_dict = json.loads(strings)[0]

    #print(f"Metadata for {image_path}:\n{strings}", flush=True)

    return python_dict


def extract_basic_image_metadata(image_path: str) -> dict:
    metadata = read_metadata(image_path)
    model_name = metadata.get("EXIF:Model", "Unknown Camera")
    datakeys = get_keys(model_name)

    #print(f"keys for {model_name}: {datakeys}", flush=True)


    creation_date = metadata.get(datakeys["created_at"], None)
    if creation_date is None:
        creation_date = datetime.now(timezone.utc).isoformat()
    elif isinstance(creation_date, str):
        try:
            creation_date = datetime.fromisoformat(creation_date)
        except ValueError:
            # If the date is not in ISO format, we can try to parse it
            creation_date = datetime.strptime(creation_date, "%Y:%m:%d %H:%M:%S")


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


    # Convert GPS coordinates to decimal format if available
    gps_lat = metadata.get(datakeys["gps"]["lat"], None)
    gps_lon = metadata.get(datakeys["gps"]["lon"], None)
    gps_rel_alt = metadata.get(datakeys["gps"]["rel_alt"], None)
    if gps_lat is None or gps_lon is None:
        coord = None
    else:
        coord = convert_coord(gps_lat, gps_lon, gps_rel_alt)

    data = {
        "created_at": creation_date,
        "width": width,
        "height": height,
        "camera_model": model_name,
        "coord": coord,
        "panoramic": check_panoramic(metadata, datakeys),
        "thermal": False,  # will be set later
        "mappable": False,  # will be set later
    }

    data["mappable"] = check_mappable(data)
    data["thermal"] = check_thermal(
        metadata, datakeys, data, os.path.basename(image_path)
    )

    # check if some values need adjustment
    if datakeys.get("adjust_data", False):
        data = adjust_data(model_name, data)

    #print(f"final data for {model_name}: {data}", flush=True)

    return data


def extract_mapping_metadata(image_path: str) -> dict:
    metadata = read_metadata(image_path)
    model_name = metadata.get("EXIF:Model", "Unknown Camera")
    datakeys = get_keys(model_name)
    data_selection = select_mapping_data(metadata, datakeys)
    if datakeys.adjust_data:
        data_selection = adjust_data(model_name, data_selection)

    return data_selection


def get_keys(model_name: str) -> dict:
    # load data from json file
    with open("app/cameramodels.json", "r") as file:
        all_keys = json.load(file)
        keys = all_keys.get(model_name, {})
        if keys == {}:
            keys = all_keys.get("default", {})
    return keys


def select_mapping_data(metadata: dict, datakeys: dict) -> dict:
    pass


def check_mappable(data: dict) -> bool:
    # TODO add  check for orientation data
    if data["coord"]is not None:
        if data["coord"].get("rel_alt", None) is not None and data["coord"].get("utm", None) is not None:
            if data["coord"]["rel_alt"] > 0:
                return True
    else:
        return False


def check_panoramic(metadata: dict, datakeys: dict) -> bool:
    projection_type = metadata.get(datakeys["projection_type"], None)
    if projection_type:
        if projection_type.lower() in ["equirectangular", "spherical"]:
            return True
    return False


def check_thermal(metadata: dict, datakeys: dict, data: dict, filename: str) -> bool:
    image_source = metadata.get(datakeys["ir"]["ir"], None)
    if image_source:
        if image_source.lower() == datakeys["ir"]["ir_value"].lower():
            return True
    elif (
        datakeys["ir"].get("ir_image_width", 0) == data["width"]
        and datakeys["ir"].get("ir_image_height", 0) == data["height"]
    ):
        return True
    elif re.search(datakeys["ir"]["ir_filename_pattern"], filename) is not None:
        return True
    return False


def adjust_data(model_name: str, data: dict) -> dict:
    match model_name:
        case "DJI Mavic 2 Pro":
            pass  # call function to adjust data for DJI Mavic 2 Pro
        case _:
            pass
    return data


def convert_coord(lat: str, lon: str, rel_alt: str) -> dict:
    lat_decimal = dms_to_decimal(lat)
    lon_decimal = dms_to_decimal(lon)

    # if rel alt is a tring convert it to float
    if rel_alt is not None:
        try:
            rel_alt = float(rel_alt)
        except ValueError:
            rel_alt = None

    zone = calculate_zone(lon_decimal)
    hemisphere = "N" if lat_decimal >= 0 else "S"
    zone_letter = latitude_to_utm_band_letter(lat_decimal)

    easting, northing, utm_crs = latlon_to_utm(lon_decimal, lat_decimal, zone)
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
        "rel_alt": rel_alt,  # Placeholder for relative altitude if available
    }


def dms_to_decimal(dms_str: str) -> float:
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


def latlon_to_utm(long: float, lat: float, zone: int) -> tuple:
    # Define the WGS84 and UTM projections using EPSG codes
    wgs84_crs = "EPSG:4326"
    utm_crs = f"EPSG:326{zone:02d}" if lat >= 0 else f"EPSG:327{zone:02d}"

    # Create a transformer object
    transformer = pyproj.Transformer.from_crs(wgs84_crs, utm_crs)

    # Transform the coordinates
    easting, northing = transformer.transform(lat, long)

    return (easting, northing, utm_crs)


def calculate_zone(long):
    return int((long + 180) / 6) + 1

def latitude_to_utm_band_letter(lat: float) -> str:
    bands = "CDEFGHJKLMNPQRSTUVWX"
    if not -80 <= lat <= 84:
        raise ValueError("Latitude out of range for UTM: must be between -80 and 84")
    index = int((lat + 80) // 8)
    return bands[index]
