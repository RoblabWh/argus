import datetime as dt
import io
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


def _extract_id(response, what: str) -> str | None:
    """Pull the id IAIS assigned out of a 200 response body, tolerantly.

    The POI endpoint documents that it returns the new id but types the body as an untyped
    object, so this accepts a bare string or a dict under any of the keys the two services
    are known to use. Returns None when nothing id-shaped is present — that is not an error,
    the record was still created.
    """
    try:
        body = response.json()
    except ValueError:
        logger.warning(f"{what} response was not JSON: {response.text[:200]}")
        return None

    if isinstance(body, str):
        return body or None
    if isinstance(body, dict):
        for key in ("id", "poi_id", "_id"):
            value = body.get(key)
            if value:
                return str(value)
    logger.info(f"{what} response carried no id: {str(body)[:200]}")
    return None


def send_geojson_poi_to_iais(
    geometry: dict, properties: dict, timeout: float = 30.0
) -> tuple[bool, str, str | None, str | None]:
    """
    PUT a point of interest to the IAIS poi service (`{DRZ_BACKEND_URL}poi/`).

    Returns (success, message, detail, poi_id) — `detail` carries the backend's own error
    text so a rejection is reported as a failure instead of being mistaken for a success,
    and `poi_id` is the id IAIS assigned, which the caller needs to attach a photo to this
    POI (the photo service takes it as a `poi_id` form field).
    """
    base = _normalize_base(config.local_settings.get("DRZ_BACKEND_URL", ""))
    if not base:
        return False, "DRZ backend is not configured", None, None
    url = base + "poi/"
    coord = geometry["coordinates"]
    coord += [0.0]
    geometry["coordinates"] = coord

    # `type` is the ORGANISATION the object originates from, not a category of object:
    # 1 is "fire brigade", not "a fire". An actual fire is therefore filed under 7 (Action),
    # which is what makes the partner situational-awareness software draw the right icon.
    # 1 (Fire), 2 (USAR), 3 (EMS), 4 (Police), 5 (Army), 6 (Other), 7 (Action), 8 (CBuilding),
    # 9 (Command), 10 (People), 11 (Resources), 12 (Active), 13 (ObjectManagement), -1 (All)
    #
    # The frontend carries it as a string ("-1", "7"); the spec declares Main as an integer
    # enum, so coerce — falling back to the raw value rather than failing the send, since
    # strings are what has been going over the wire until now.
    try:
        type = int(properties['type'])
    except (TypeError, ValueError):
        type = properties['type']
    subtype = properties['subtype']
    # SUSPECTED (False) / ACUTE (True). Required by the schema; defaults to SUSPECTED, which
    # is the value this was hardcoded to before the share dialog exposed it.
    danger_level = bool(properties.get('danger_level', False))
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
        return False, f"DRZ backend did not respond within {timeout}s", "timeout", None
    except requests.exceptions.ConnectionError as e:
        return False, "Could not connect to the DRZ backend", str(e), None
    except requests.exceptions.RequestException as e:
        return False, "Request to the DRZ backend failed", str(e), None

    if response is None:
        return False, "DRZ authentication failed — check the credentials in Settings", None, None

    if response.status_code != 200:
        logger.warning(f"POI upload failed (HTTP {response.status_code}): {response.text[:200]}")
        return (
            False,
            f"DRZ backend rejected the POI (HTTP {response.status_code})",
            response.text[:200],
            None,
        )

    # The spec types the 200 body as an untyped object but documents "the ID for the newly
    # created POI is returned in the response body"; the sibling photo service answers with
    # {"message": ..., "id": ...}. Accept either a bare id string or a dict under any of the
    # plausible keys, and log the raw body so the shape is settled by the first real run.
    poi_id = _extract_id(response, "POI")
    return True, "POI sent to the DRZ system", None, poi_id

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


def send_map_to_iais(map:Map, layer:str, report_id:int, workspace: str | None = None):
    """Publish a map's GeoTIFF as a GeoServer coverage store.

    `workspace` overrides the configured DRZ_GEOSERVER_WORKSPACE for this one upload
    (the share dialog offers it behind a lock); None falls back to the setting, and an
    unset setting falls back to "DRZ" — the value this was hardcoded to.
    """
    logger.info("Sending file to iais")
    workspace = (workspace or config.local_settings.get("DRZ_GEOSERVER_WORKSPACE") or "DRZ").strip()
    message = f"Sent map to layer '{layer}' in workspace '{workspace}'"

    geotiff_path = get_geo_tiff(map)
    logger.info(geotiff_path)
    if geotiff_path == None:
        # Raise rather than return a sentinel string — the router turns an exception into
        # a {"success": False} response, while a returned string used to read as a success.
        raise ValueError("Could not build a GeoTIFF for this map")
    geo_server_url = config.local_settings['DRZ_BACKEND_URL']
    logger.info(f"geo_server_url {geo_server_url}, workspace '{workspace}', layer '{layer}'")

    # try:
    geo = Geoserver(f"{geo_server_url}/geoserver")#, username=geo_server_username, password=geo_server_password)
    # filename = os.path.basename(geotiff_path)
    # Raises GeoserverException on anything but 201 (an unknown workspace included); the
    # router turns that into a {"success": False} response carrying the server's own text.
    response = geo.create_coveragestore(layer_name=layer, path=geotiff_path, workspace=workspace)
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


# Above this the upload is re-encoded. Chosen so a normal frame (median 6 MB on this
# deployment) ships byte-for-byte, while the outliers that broke the upload are tamed.
UPLOAD_SIZE_TARGET = 8 * 1024 * 1024
# Quality ladder for that re-encode. 80 is the floor: below it JPEG artefacts start to
# matter for an image an analyst may zoom into. Resolution is never reduced.
UPLOAD_QUALITY_LADDER = (92, 90, 85, 80)
# Extensions Pillow will hand us as a JPEG-compatible stream. DJI writes MPO (a JPEG with
# extra embedded frames) behind a .JPG name, which is exactly why these files are so large.
_JPEG_SUFFIXES = (".jpg", ".jpeg")


def _encode_jpeg(im, quality: int, info: dict) -> bytes:
    """Encode `im` as JPEG at `quality`, carrying its metadata across.

    EXIF and XMP are not cosmetic here: Argus parses them itself for flight and gimbal data,
    and the DRZ side is entitled to the same provenance. Pillow drops both unless they are
    passed back explicitly.
    """
    buf = io.BytesIO()
    save_kwargs = {"quality": quality, "optimize": True}
    for key in ("exif", "xmp", "icc_profile"):
        value = info.get(key)
        if value:
            save_kwargs[key] = value
    im.save(buf, "JPEG", **save_kwargs)
    return buf.getvalue()


@contextmanager
def _prepared_upload(image_path: str):
    """
    Yield a path to an uploadable JPEG version of `image_path`.

    Three cases:
      * Not a JPEG at all (the stella worker writes 5760x2880 PNG keyframes) — convert.
      * A JPEG/MPO already within UPLOAD_SIZE_TARGET — yield it untouched, so the common
        case is byte-exact and costs nothing.
      * A larger JPEG/MPO — re-encode the primary frame at its native resolution, stepping
        down UPLOAD_QUALITY_LADDER until it fits or the floor is reached. DJI frames are MPO
        containers whose extra embedded frames are pure upload weight: a 14 MB file becomes
        ~5 MB at q90 with no change in dimensions.

    Resolution is deliberately never reduced — an analyst needs to zoom in — so an image that
    cannot reach the target at q80 is simply sent at whatever q80 produces.
    """
    suffix = os.path.splitext(image_path)[1].lower()
    size = os.path.getsize(image_path)

    if suffix in _JPEG_SUFFIXES and size <= UPLOAD_SIZE_TARGET:
        yield image_path
        return

    tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
    tmp.close()
    try:
        # Our own files off the local volume, not untrusted input. The 14400x2 panoramas are
        # ~103 MP, over Pillow's DecompressionBomb warning threshold, and Pillow refuses
        # outright above twice that.
        previous_limit = Image.MAX_IMAGE_PIXELS
        Image.MAX_IMAGE_PIXELS = None
        try:
            with Image.open(image_path) as img:
                info = dict(img.info)
                if suffix in _JPEG_SUFFIXES:
                    img.load()
                    data = None
                    for quality in UPLOAD_QUALITY_LADDER:
                        data = _encode_jpeg(img, quality, info)
                        if len(data) <= UPLOAD_SIZE_TARGET:
                            break
                    with open(tmp.name, "wb") as fh:
                        fh.write(data)
                    logger.info(
                        f"Re-encoded {os.path.basename(image_path)} for upload at q{quality}: "
                        f"{size} -> {len(data)} bytes ({img.width}x{img.height}, unchanged)"
                    )
                else:
                    img.convert("RGB").save(tmp.name, "JPEG", quality=90)
                    logger.info(
                        f"Converted {os.path.basename(image_path)} to JPEG for upload "
                        f"({size} -> {os.path.getsize(tmp.name)} bytes)"
                    )
        finally:
            Image.MAX_IMAGE_PIXELS = previous_limit
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
    poi_id: str | None = None,
    direction: int | None = None,
    # (connect, read). The connect value has to cover the whole upload, not just the TCP
    # handshake: urllib3 keeps the connect timeout on the socket for the entire request-send
    # phase and only swaps in the read timeout once the body is out (connectionpool.py sets
    # conn.timeout = connect_timeout up front, read_timeout only before reading the response).
    # At 5s that capped uploads at ~13 MB on a 2.6 MB/s link, which is the bug this fixes.
    timeout: tuple[float, float] = (45.0, 120.0),
) -> tuple[bool, str, str | None]:
    """
    PUT an image to the IAIS photo service (`{DRZ_BACKEND_URL}photo/`).

    `projection` is "panorama_360_equirectangular" for 360° panoramas, "normal" otherwise.
    Passing `photo_id` makes IAIS update that photo instead of creating a duplicate.
    Passing `poi_id` links the photo to that POI, so it shows up under
    `GET {BASE}photo/poi_related/{poi_id}`.
    `direction` is the compass heading the photo was taken along, in degrees.

    Returns (success, message, iais_photo_id).
    """
    base = config.DRZ_BACKEND_URL
    if not base:
        return False, "DRZ backend is not configured", None
    if not os.path.exists(image_path):
        return False, f"Image not found: {os.path.basename(image_path)}", None

    base = _normalize_base(base)
    url = base + "photo/"

    # geometry_type/crs_type/crs_code are left to the service's own defaults (Point, EPSG,
    # 4326). `direction` is only sent when the caller knows it: SLAM panoramas have no north
    # reference, while a mapping image has the camera yaw from EXIF.
    fields = {
        "coordinates": _format_coordinates(lat, lon),
        "name": name,
        "projection": projection,
    }
    if description:
        fields["description"] = description
    if photo_id:
        fields["id"] = photo_id
    if poi_id:
        fields["poi_id"] = poi_id
    if direction is not None:
        # The service takes whole degrees; normalize so a negative or >360 yaw is accepted.
        fields["direction"] = str(int(round(direction)) % 360)

    logger.info(f"Sending photo '{name}' to {url} at ({lat}, {lon}), projection={projection}")

    upload_name = os.path.splitext(os.path.basename(image_path))[0] + ".jpg"
    try:
        prepared = _prepared_upload(image_path)
        # Entered separately from the request so a genuine read/convert failure keeps its own
        # message. Every requests exception is also an OSError (RequestException subclasses
        # it), so a single combined `except OSError` would swallow the network errors below
        # and report them as "could not read the image" — which is exactly what used to
        # happen to oversized uploads.
        jpeg_path = prepared.__enter__()
    except OSError as e:
        return False, f"Could not read or convert the image: {e}", None

    try:
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
    except requests.exceptions.Timeout:
        return False, f"Upload to DRZ timed out after {timeout[1]}s", None
    except requests.exceptions.ConnectionError as e:
        # Includes a socket timeout part-way through the body — see the timeout note on the
        # signature. The upload size, not the connection, is usually the culprit.
        return False, "Could not connect to the DRZ backend", str(e)
    except requests.exceptions.RequestException as e:
        return False, "Upload request failed", str(e)
    except OSError as e:
        return False, f"Could not read the prepared upload: {e}", None
    finally:
        prepared.__exit__(None, None, None)

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
