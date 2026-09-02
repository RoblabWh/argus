import datetime as dt
import json
import tempfile
import threading
import time
from contextlib import contextmanager

import requests


import logging
logger = logging.getLogger(__name__)
from app.config import config
from app.models.map import Map 
import os
import cv2
import rasterio
from PIL import Image
from geo.Geoserver import Geoserver


def send_geojson_poi_to_iais(
    geometry: dict, properties: dict, timeout: float = 30.0
) -> tuple[bool, str, str | None]:
    """
    PUT a point of interest to the IAIS poi service (`{DRZ_BACKEND_URL}poi/`).

    Returns (success, message, detail) like the other DRZ senders, so a rejection by the
    backend is reported as a failure instead of being mistaken for a success.
    """
    base = _normalize_base(config.local_settings.get("DRZ_BACKEND_URL", ""))
    if not base:
        return False, "DRZ backend is not configured", None
    url = base + "poi/"
    coord = geometry["coordinates"]
    coord += [0.0]
    geometry["coordinates"] = coord

    type = properties['type'] # 1 (Fire), 2 (USAR), 3 (EMS), 4 (Police), 5 (Army), 6 (Other), 7 (Action), 8 (CBuilding), 9 (Command), 10 (People), 11 (Resources), 12 (Active), 13 (ObjectManagement), -1 (All)
    subtype = properties['subtype'] 
    danger_level = False #properties['danger_level']
    detection = properties['detection']
    name = properties['name']
    description = properties['description']
    datetime = properties['datetime']
    logger.info(f"Preparing to send POI to Iais with type: {type}, subtype: {subtype}, danger_level: {danger_level}, detection: {detection}, name: {name}, description: {description}, datetime: {datetime}")
    #convert datetime from 03.08.2024 10:00 to 2024-03-08T10:00:00
    #dt.datetime.strptime(datetime, '%Y-%m-%dT%H:%M').isoformat()
    #logger.info(f"Converted datetime: {datetime}")

    #Subtypes 
    #0 Person
        #1"Person in distress (trapped/buried)"
        #2"Person injured"
        #3"Person dead"
        #4"Missing person"
        #5"Buried person"
        #6"Presumably buried person"
    #2 Vehicle
        #0"Land vehicle (car, truck, trailer)"
        #1"Rail vehicle (locomotive, wagon)"
        #2"Water vehicle (boat, ship)"
        #3"Air vehicle (airplane, helicopter)"
        #4"Helicopter"
    #4 Fire
        #0"Fire (small)"
        #1"Fire (medium)"
        #2"Fire (large)"

    # danger_level SUSPECTED (FALSE), ACUTE (TRUE)
    # detection 0 (AUTO), 1 (MANUELL), 2 (VERIFIED)


    # if type == "human":
    #     type = 10
    #     subtype = "Person"
    #     danger_level = False
    # elif type == "fire":
    #     type = 1
    #     subtype = "Fire (medium)"
    #     danger_level = False
    # elif type == "vehicle":
    #     type = -1
    #     subtype = "Land vehicle (car, truck, trailer)"
    #     danger_level = False
    # else:
    #     raise Exception("Unknown type", type)

    crs = {
        "properties": {
            "code": 4326
        },
        "type": "EPSG"
    }

    properties = {
        "type": type,
        "subtype": subtype,
        "danger_level": danger_level,
        "detection": detection,
        "name": name,
        "description": description,
        "datetime": datetime
    }

    type = "Feature"

    data = {
        "crs": crs,
        "geometry": geometry,
        "properties": properties,
        "type": type
    }
    logger.info(f"Sending POI '{name}' to {url}")

    def send(token: str):
        return requests.put(
            url,
            headers={
                "accept": "*/*",
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token}",
            },
            data=json.dumps(data),
            timeout=timeout,
        )

    try:
        response = _send_with_auth(base, send)
    except requests.exceptions.Timeout:
        return False, f"DRZ backend did not respond within {timeout}s", "timeout"
    except requests.exceptions.ConnectionError as e:
        return False, "Could not connect to the DRZ backend", str(e)
    except requests.exceptions.RequestException as e:
        return False, "Request to the DRZ backend failed", str(e)

    if response is None:
        return False, "DRZ authentication failed — check the credentials in Settings", None

    if response.status_code != 200:
        logger.warning(f"POI upload failed (HTTP {response.status_code}): {response.text[:200]}")
        return (
            False,
            f"DRZ backend rejected the POI (HTTP {response.status_code})",
            response.text[:200],
        )

    return True, "POI sent to the DRZ system", None

# Cached DRZ access tokens, keyed by (base url, username).
#
# The registration service hands out tokens with `expires_in` ~5 hours, so re-authenticating
# on every send throws away almost all of that. Entries are refreshed a minute before the
# server's own expiry, and dropped whenever the backend rejects one (see `_send_with_auth`)
# or the credentials change (see `invalidate_token`, called from PUT /settings/drz).
_token_cache: dict[tuple[str, str], tuple[str, float]] = {}
_token_lock = threading.Lock()
_TOKEN_SKEW = 60.0
_DEFAULT_TOKEN_TTL = 3600.0


def _normalize_base(url: str) -> str:
    """Trailing-slash-normalized backend base url, so `{base}poi/` style joins are safe."""
    if not url:
        return ""
    return url if url.endswith("/") else url + "/"


def _fetch_token(base: str, username: str, password: str, timeout: float = 10.0):
    """
    POST the credentials to the one shared token endpoint and return (token, expires_at).

    All three IAIS services (registration, poi, photo) accept the same bearer token; it is
    always issued by `{BASE}registration/token`, never by a per-service `token` path.
    Returns (None, 0.0) if the backend refuses. Transport errors propagate to the caller.
    """
    url = _normalize_base(base) + "registration/token"
    response = requests.post(url, data={"username": username, "password": password}, timeout=timeout)
    if response.status_code != 200:
        logger.info(f"DRZ token request to {url} failed with HTTP {response.status_code}")
        return None, 0.0

    body = response.json()
    token = body.get("access_token")
    if not token:
        logger.info(f"DRZ token response from {url} contained no access_token")
        return None, 0.0

    try:
        ttl = float(body.get("expires_in") or _DEFAULT_TOKEN_TTL)
    except (TypeError, ValueError):
        ttl = _DEFAULT_TOKEN_TTL
    return token, time.monotonic() + ttl


def authenticate_backend(
    url: str | None = None,
    username: str | None = None,
    password: str | None = None,
    force_refresh: bool = False,
) -> str | None:
    """
    Return a DRZ access token, reusing the cached one while it is still valid.

    `url` is the backend *base* url (not a resource url such as `{BASE}photo/`); it falls
    back to the configured one, as do the credentials. Pass `force_refresh=True` to bypass
    the cache after the backend has rejected a token.
    """
    if url is None:
        url = config.local_settings.get("DRZ_BACKEND_URL", "")
    if username is None:
        username = config.local_settings["DRZ_BACKEND_USERNAME"]
    if password is None:
        password = config.local_settings["DRZ_BACKEND_PASSWORD"]

    base = _normalize_base(url)
    key = (base, username)

    if not force_refresh:
        with _token_lock:
            cached = _token_cache.get(key)
        if cached and time.monotonic() < cached[1] - _TOKEN_SKEW:
            return cached[0]

    token, expires_at = _fetch_token(base, username, password)
    with _token_lock:
        if token:
            _token_cache[key] = (token, expires_at)
        else:
            _token_cache.pop(key, None)
    if not token:
        logger.info("token authentication failed")
    return token


def invalidate_token(url: str | None = None, username: str | None = None) -> None:
    """Drop cached tokens. With no arguments, clears the whole cache."""
    if url is None and username is None:
        with _token_lock:
            _token_cache.clear()
        return

    base = _normalize_base(url if url is not None else config.local_settings.get("DRZ_BACKEND_URL", ""))
    if username is None:
        username = config.local_settings["DRZ_BACKEND_USERNAME"]
    with _token_lock:
        _token_cache.pop((base, username), None)


def _send_with_auth(base: str, send):
    """
    Run `send(token)` with a cached token, retrying once with a fresh one on 401/403.

    `send` must build its request from scratch on each call — the photo upload streams a
    file handle, which cannot be replayed. Returns the final `requests.Response`, or None
    if no token could be obtained at all.
    """
    token = authenticate_backend(base)
    if not token:
        return None

    response = send(token)
    if response.status_code not in (401, 403):
        return response

    # The backend rejected the token: it may have been revoked or expired early. Re-auth
    # once and replay; a second rejection is a real failure and is returned as-is.
    logger.info(f"DRZ rejected the cached token (HTTP {response.status_code}); re-authenticating once")
    token = authenticate_backend(base, force_refresh=True)
    if not token:
        return response
    return send(token)


def try_drz_authenticate(
    url: str, username: str, password: str, timeout: float = 5.0
) -> tuple[bool, str, str | None]:
    """
    Single-attempt authentication against the DRZ backend.
    Normalizes the trailing slash on the URL like the save endpoint does.
    Returns (success, message, detail). Does not read or write config.
    """
    if not url:
        return False, "DRZ backend URL is empty", None

    url = _normalize_base(url) + "registration/token"
    logger.info(f"Trying to authenticate against DRZ backend at {url} with username {username}")
    try:
        response = requests.post(
            url,
            data={"username": username, "password": password},
            timeout=timeout,
        )
    except requests.exceptions.Timeout:
        return False, f"Connection timed out after {timeout}s", "timeout"
    except requests.exceptions.ConnectionError as e:
        return False, "Could not connect to DRZ backend", str(e)
    except requests.exceptions.RequestException as e:
        return False, "Request failed", str(e)

    if response.status_code == 200 and response.json().get("access_token"):
        return True, "Authenticated successfully", None
    if response.status_code in (400, 401, 403):
        return False, "Invalid DRZ username or password", f"HTTP {response.status_code}"
    return False, f"Unexpected response from DRZ backend (HTTP {response.status_code})", response.text[:200]


def send_map_to_iais(map:Map, layer:str, report_id:int):
    logger.info("Sending file to iais")
    message = "Sending maps to iais"

    geotiff_path = get_geo_tiff(map)
    logger.info(geotiff_path)
    #send file to iais
    settings = config.local_settings['DRZ_BACKEND_URL']
    logger.info(settings)
    if geotiff_path == None:
        return "failed to send"
    geo_server_url = config.local_settings['DRZ_BACKEND_URL']
    logger.info(f"geo_server_url{geo_server_url}")

    # try:
    geo = Geoserver(f"{geo_server_url}/geoserver")#, username=geo_server_username, password=geo_server_password)
    # filename = os.path.basename(geotiff_path)
    response = geo.create_coveragestore(layer_name=layer, path=geotiff_path, workspace='DRZ')
    logger.info(response)
    # except Exception as e:
    #     logger.info(f"Error while sending file to iais: {e}")
    #     message += f"\nError while sending file to iais: {e}"
    return message

def get_geo_tiff(map:Map):
    file_path = map.url.replace('png', 'tif')
    mapping = map.bounds

    
    #test if file exists
    #if not os.path.exists(file_path):
    if not create_geo_tiff(map): return None
    
    print(f"File {file_path} exists", flush=True)
    return file_path

def create_geo_tiff(map:Map):
    img_path = map.url
    geotiff_path = map.url.replace('png', 'tif')
    bounds = map.bounds
    corners = bounds["corners"]["gps"]


    logger.info(f"trying to convert map {img_path} into geotiff based on bounds ({bounds}) with corners: {corners}")


    img = cv2.imread(img_path, cv2.IMREAD_UNCHANGED)
    if img is None:
        raise ValueError("Error loading image. Check the file path.")

    # Ensure the image has 4 channels (RGBA)
    if img.shape[-1] == 3:
        img = cv2.cvtColor(img, cv2.COLOR_BGR2BGRA)
    elif img.shape[-1] == 4:
        img = cv2.cvtColor(img, cv2.COLOR_BGRA2RGBA)

    height, width = img.shape[:2]

    #get the smallest and largest lat and lon from the corners
    min_lon = min([corner[0] for corner in corners])
    min_lat = min([corner[1] for corner in corners])
    max_lon = max([corner[0] for corner in corners])
    max_lat = max([corner[1] for corner in corners])

    # Compute affine transformation
    transform = rasterio.transform.from_bounds(min_lon, min_lat, max_lon, max_lat, width, height)

    # Create GeoTIFF with affine transformation
    with rasterio.open(
            geotiff_path, 'w', driver='GTiff',
            height=height, width=width,
            count=4, dtype=img.dtype.name,  # Assuming RGBA
            crs='EPSG:4326',  # WGS84 coordinate system
            transform=transform,  # Now using a valid affine transform
            compress='DEFLATE',
            tiled=True,
    ) as dst:
        for band in range(4):  # RGBA bands
            dst.write(img[:, :, band], band + 1)
    
    return True

def _format_coordinates(lat: float, lon: float) -> str:
    """
    Encode a point for the IAIS photo service's `coordinates` form field.

    The OpenAPI spec types this as a bare string with no format or example, and the
    backend is only reachable during integration sprints, so this mirrors the one
    encoding we know IAIS accepts: `send_geojson_poi_to_iais` above sends a GeoJSON
    position with lon first and a Z value appended (`coord += [0.0]`).

    If the sprint shows the photo service wants something else, this is the only
    place that needs to change.
    """
    return json.dumps([lon, lat, 0.0])


@contextmanager
def _as_jpeg(image_path: str):
    """
    Yield a JPEG version of `image_path`.

    The IAIS photo service documents `image` as "Image file to upload as jpg", but the
    stella worker writes keyframes as PNG (5760x2880, >10 MB each), so those are
    converted to a temporary JPEG first — which also cuts the upload to a fraction of
    the size. Files that are already JPEG are passed through untouched.
    """
    if os.path.splitext(image_path)[1].lower() in (".jpg", ".jpeg"):
        yield image_path
        return

    tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
    tmp.close()
    try:
        with Image.open(image_path) as img:
            img.convert("RGB").save(tmp.name, "JPEG", quality=90)
        logger.info(
            f"Converted {os.path.basename(image_path)} to JPEG for upload "
            f"({os.path.getsize(image_path)} -> {os.path.getsize(tmp.name)} bytes)"
        )
        yield tmp.name
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass


def send_photo_to_iais(
    image_path: str,
    name: str,
    lat: float,
    lon: float,
    projection: str = "panorama_360_equirectangular",
    description: str | None = None,
    photo_id: str | None = None,
    timeout: tuple[float, float] = (5.0, 120.0),
) -> tuple[bool, str, str | None]:
    """
    PUT an image to the IAIS photo service (`{DRZ_BACKEND_URL}photo/`).

    `projection` is "panorama_360_equirectangular" for 360° panoramas, "normal" otherwise.
    Passing `photo_id` makes IAIS update that photo instead of creating a duplicate.

    Returns (success, message, iais_photo_id).
    """
    base = config.DRZ_BACKEND_URL
    if not base:
        return False, "DRZ backend is not configured", None
    if not os.path.exists(image_path):
        return False, f"Image not found: {os.path.basename(image_path)}", None

    base = _normalize_base(base)
    url = base + "photo/"

    # `direction` is deliberately omitted: SLAM panoramas have no north reference and the
    # service already defaults it to 0 (north). Same for geometry_type/crs_type/crs_code.
    fields = {
        "coordinates": _format_coordinates(lat, lon),
        "name": name,
        "projection": projection,
    }
    if description:
        fields["description"] = description
    if photo_id:
        fields["id"] = photo_id

    logger.info(f"Sending photo '{name}' to {url} at ({lat}, {lon}), projection={projection}")

    upload_name = os.path.splitext(os.path.basename(image_path))[0] + ".jpg"
    try:
        with _as_jpeg(image_path) as jpeg_path:

            def send(token: str, _path=jpeg_path):
                # Opened per attempt: a retry after a 401 replays the upload, and the
                # handle from the first attempt is already consumed.
                with open(_path, "rb") as fh:
                    # No explicit Content-Type — requests sets the multipart boundary itself.
                    return requests.put(
                        url,
                        headers={"accept": "*/*", "Authorization": f"Bearer {token}"},
                        data=fields,
                        files={"image": (upload_name, fh, "image/jpeg")},
                        timeout=timeout,
                    )

            response = _send_with_auth(base, send)
    except OSError as e:
        return False, f"Could not read or convert the image: {e}", None
    except requests.exceptions.Timeout:
        return False, f"Upload to DRZ timed out after {timeout[1]}s", None
    except requests.exceptions.ConnectionError as e:
        return False, "Could not connect to the DRZ backend", str(e)
    except requests.exceptions.RequestException as e:
        return False, "Upload request failed", str(e)

    if response is None:
        return False, "DRZ authentication failed — check the credentials in Settings", None

    if response.status_code != 200:
        logger.warning(f"Photo upload failed (HTTP {response.status_code}): {response.text[:200]}")
        return (
            False,
            f"DRZ backend rejected the upload (HTTP {response.status_code}): {response.text[:200]}",
            None,
        )

    try:
        body = response.json()
    except ValueError:
        return True, "Photo uploaded, but the response could not be parsed", None

    returned_id = body.get("id")
    return True, body.get("message") or "Photo uploaded successfully", returned_id
