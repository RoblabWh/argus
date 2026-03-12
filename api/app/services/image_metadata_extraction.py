import json
import pyproj
import pyexifinfo as p
import re
from datetime import datetime, timezone
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

CAMERA_CONFIGS_DIR = Path("app/camera_configs")


def _read_metadata(image_path: str) -> dict:
    data = p.get_json(image_path)
    if not data:
        raise ValueError("No metadata found in the image file.")

    strings = json.dumps(data, sort_keys=True, indent=4, separators=(",", ": "))
    python_dict = json.loads(strings)[0]

    logger.debug(f"Metadata for {image_path}:\n{strings}")

    return python_dict


def _model_name_to_filename(model_name: str) -> str:
    """Sanitize camera model name to a valid filename."""
    safe = re.sub(r"[^\w\-]", "_", model_name)
    return safe + ".json"


def _load_model_config(model_name: str, metadata: dict) -> dict:
    """Load per-model config, auto-discovering and saving if not found."""
    config_path = CAMERA_CONFIGS_DIR / _model_name_to_filename(model_name)
    if config_path.exists():
        with config_path.open() as f:
            return json.load(f)
    logger.info(f"No config for '{model_name}', running auto-discovery.")
    return _auto_discover_config(model_name, metadata)


def _auto_discover_config(model_name: str, metadata: dict) -> dict:
    """Try all candidate keys from _default.json against actual metadata, save result."""
    default_path = CAMERA_CONFIGS_DIR / "_default.json"
    with default_path.open() as f:
        template = json.load(f)

    config = {
        "_model": model_name,
        "_auto_discovered": True,
        "adjust_data": False,
        "fov_correction": 1.0,
        "fallbacks": {"thermal": {}},
    }

    # Simple scalar fields
    for field in ("created_at", "width", "height", "projection_type"):
        for candidate in template.get(field, []):
            if candidate in metadata:
                config[field] = candidate
                break
        else:
            logger.warning(f"Could not auto-discover field '{field}' for model '{model_name}'")
            config[field] = None

    # Nested dict fields (gps, camera_properties, orientation)
    for section in ("gps", "camera_properties", "orientation"):
        config[section] = {}
        for key, candidates in template.get(section, {}).items():
            for candidate in candidates:
                if candidate in metadata:
                    config[section][key] = candidate
                    break
            if key not in config[section]:
                logger.warning(f"Could not auto-discover {section} field '{key}' for model '{model_name}'")
                config[section][key] = None

    # IR — special handling
    ir_template = template.get("ir", {})
    ir_config = {}
    for pair in ir_template.get("tag_value_candidates", []):
        if pair["tag"] in metadata:
            ir_config["ir"] = pair["tag"]
            ir_config["ir_value"] = pair["value"]
            break
    ir_config["ir_filename_pattern"] = ir_template.get("filename_pattern_default", "")
    ir_config["ir_scale"] = ir_template.get("ir_scale_default", 0.5)
    config["ir"] = ir_config

    # Save
    save_path = CAMERA_CONFIGS_DIR / _model_name_to_filename(model_name)
    CAMERA_CONFIGS_DIR.mkdir(exist_ok=True)
    with save_path.open("w") as f:
        json.dump(config, f, indent=2)
    logger.info(f"Saved auto-discovered config to {save_path}")

    return config


def get_ir_scale(model_name: str) -> float:
    """Return ir_scale for a known model config, or 0.5 default."""
    config_path = CAMERA_CONFIGS_DIR / _model_name_to_filename(model_name)
    if config_path.exists():
        with config_path.open() as f:
            return json.load(f).get("ir", {}).get("ir_scale", 0.5)
    return 0.5


def extract_image_metadata(image_path: str) -> dict:
    metadata = _read_metadata(image_path)
    model_name = metadata.get("EXIF:Model", "Unknown Camera")
    config = _load_model_config(model_name, metadata)

    logger.debug(f"keys for {model_name}: {config}")

    creation_date = _extract_creation_date(metadata, config)
    logger.debug(f"extracted creation_date for {model_name}: {creation_date}")
    width, height = _extract_dimensions(metadata, config)
    logger.debug(f"extracted dimensions for {model_name}: width={width}, height={height}")
    coord = _extract_coordinates(metadata, config)
    logger.debug(f"extracted coordinates for {model_name}: {coord}")    


    data = {
        "created_at": creation_date,
        "width": width,
        "height": height,
        "camera_model": model_name,
        "coord": coord,
        "panoramic": _check_panoramic(metadata, config),
        "thermal": False,  # will be set later
        "mappable": False,  # will be set later
    }
    logger.debug(f"extracted data for {model_name}: {data}")

    data["thermal"] = _check_thermal(
        metadata, config, data, Path(image_path).name
    )
    logger.debug(f"Image thermal check for {model_name}: {data['thermal']}")

    try:
        mappable, mapping_data = _extract_mapping_data(metadata, config, data)
        if mapping_data:
            data["mappable"] = mappable
            data["mapping_data"] = mapping_data
    except Exception as e:
        logger.warning(f"Error extracting mapping data: {e}")
        mapping_data = None

    logger.debug(f"Image mappable check for {model_name}: {data['mappable']}")

    # check if some values need adjustment
    if config.get("adjust_data", False):
        data = _adjust_data(model_name, data)
    logger.debug(f"adjusted data for {model_name}: {data}")
    logger.debug(f"final data for {model_name}: {data}")

    return data


def _extract_creation_date(metadata: dict, config: dict) -> str:
    creation_date = metadata.get(config.get("created_at"), None)
    if creation_date is None:
        return datetime.now(timezone.utc).isoformat()
    elif isinstance(creation_date, str):
        try:
            return datetime.fromisoformat(creation_date)
        except ValueError:
            # If the date is not in ISO format, we can try to parse it
            return datetime.strptime(creation_date, "%Y:%m:%d %H:%M:%S")

    return None


def _extract_dimensions(metadata: dict, config: dict) -> tuple:
    width = metadata.get(config.get("width"), None)
    height = metadata.get(config.get("height"), None)

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


def _extract_coordinates(metadata: dict, config: dict) -> dict:
    gps_lat = metadata.get(config["gps"]["lat"], None)
    gps_lon = metadata.get(config["gps"]["lon"], None)
    gps_alt = metadata.get(config["gps"]["alt"], None)
    gps_rel_alt = metadata.get(config["gps"]["rel_alt"], None)
    if gps_lat is None or gps_lon is None:
        coord = None
    else:
        coord = _convert_coord(gps_lat, gps_lon, gps_alt, gps_rel_alt)

    return coord


def _check_mappable(data: dict) -> bool:
    # TODO add  check for orientation data
    if data["coord"] is not None:
        if data["coord"].get("rel_alt", None) is not None and data["coord"].get("utm", None) is not None:
            if data["coord"]["rel_alt"] > 0:
                return True
    else:
        return False


def _check_panoramic(metadata: dict, config: dict) -> bool:
    if "projection_type" not in config:
        return False
    projection_type = metadata.get(config["projection_type"], None)
    if projection_type:
        if projection_type.lower() in ["equirectangular", "spherical"]:
            return True
    return False


def _check_thermal(metadata: dict, config: dict, data: dict, filename: str) -> bool:
    logger.debug(f"comparing: has ir config: {'ir' in config}, ir_value: {config.get('ir', {}).get('ir_value', None)}, ")
    if "ir" not in config:
        return False
    if config['ir'].get('ir_value', None) is not None:
        logger.info(f"Checking if image {filename} is thermal based on ir_value")
        image_source = metadata.get(config["ir"]["ir"], None)
        logger.info(f"Image source: {image_source}")
        if image_source:
            if image_source.lower() == config["ir"]["ir_value"].lower():
                return True
    elif config["ir"].get("ir_image_width", 0) == data["width"] \
        and config["ir"].get("ir_image_height", 0) == data["height"]:
        return True
    elif re.search(config["ir"]["ir_filename_pattern"], filename) is not None:
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

    # if rel alt is a string convert it to float
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


def _extract_mapping_data(metadata: dict, config: dict, data: dict) -> tuple:
    mapping_data = {}
    coord = data["coord"]
    thermal = data["thermal"]

    mapping_data["rel_altitude"] = coord.get("rel_alt", None)
    mapping_data["altitude"] = coord.get("alt", None)

    if mapping_data["rel_altitude"] is None:
        mapping_data["rel_altitude_method"] = "manual"
    else:
        mapping_data["rel_altitude_method"] = "exif"

    fov = metadata.get(config["camera_properties"]["fov"], None)
    if fov is None:
        fallback_fov = None
        if thermal:
            fallback_fov = _load_fallback('fov', config, thermal)
            logger.debug(f"FOV not found in metadata, using fallback value: {fallback_fov}")
        if fallback_fov is None:
            logger.warning("FOV missing and no fallback available — marking as manual")
            mapping_data["fov"] = None
            mapping_data["fov_method"] = "manual"
        else:
            mapping_data["fov"] = fallback_fov
            mapping_data["fov_method"] = "fallback"
    else:
        fov = float(fov.split()[0])
        if config.get("fov_correction", 1.0) != 1.0:
            fov *= config["fov_correction"]
        mapping_data["fov"] = fov
        mapping_data["fov_method"] = "exif"

    orientation_keys = config["orientation"]
    for key in ("uav_roll", "uav_yaw", "uav_pitch"):
        value = metadata.get(orientation_keys[key], None)
        if value is None:
            logger.warning(f"Orientation value for {key} is missing, cannot extract mapping data.")
            return False, None
        try:
            mapping_data[key] = float(value)
        except (TypeError, ValueError):
            logger.warning(f"Orientation value for {key} is not a valid float, cannot extract mapping data.")
            return False, None

    for key in ("cam_roll", "cam_yaw", "cam_pitch"):
        value = metadata.get(orientation_keys[key], None)
        if value is None:
            continue
        try:
            mapping_data[key] = float(value)
        except (TypeError, ValueError):
            logger.warning(f"Orientation value for {key} is not a valid float, skipping this value.")
            continue

    for uav_key, cam_key in [("uav_yaw", "cam_yaw"), ("uav_roll", "cam_roll")]:
        if uav_key in mapping_data and cam_key in mapping_data:
            yaw_diff = mapping_data[uav_key] - mapping_data[cam_key]
            if abs(yaw_diff) > 140:
                mapping_data[cam_key] = _normalize_angle(mapping_data[cam_key] + 180)

    mapping_data["cam_pitch_method"] = "exif" if "cam_pitch" in mapping_data else "manual"
    mapping_data["cam_yaw_method"]   = "exif" if "cam_yaw"   in mapping_data else "uav"
    mapping_data["cam_roll_method"]  = "exif" if "cam_roll"  in mapping_data else "uav"

    mappable = (
        mapping_data.get("rel_altitude") is not None
        and mapping_data.get("fov") is not None
        and mapping_data.get("cam_pitch") is not None
    )
    return mappable, mapping_data


def _load_fallback(key: str, config: dict, thermal: bool) -> float | None:
    section = "thermal" if thermal else "optical"
    return config.get("fallbacks", {}).get(section, {}).get(key)
