import datetime as dt
import json
import requests

#iais_url = "http://iais-backend:8000/api/"
iais_url = "https://fake-rlw.rettungsrobotik.de/"
iais_url = "https://eve.iais.fraunhofer.de/"
import logging
logger = logging.getLogger(__name__)
from app.config import config
from app.models.map import Map 
import os
import cv2
import rasterio
from geo.Geoserver import Geoserver


def send_geojson_poi_to_iais(geometry: dict, properties: dict):


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
    print(data, flush=True)

    url = iais_url + 'poi/'
    headers = {
        "accept": "*/*",
        "Content-Type": "application/json"
    }
    response = requests.put(url, headers=headers, data=json.dumps(data), auth=("development", "LookMomNoVPN!"))

    if response.status_code == 200:
        return "PUT request successful!"
    else:
        print(f"PUT request failed with status code {response.status_code}", flush=True)
        return requests.json()




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
    geo = Geoserver()#, username=geo_server_username, password=geo_server_password)
    # filename = os.path.basename(geotiff_path)
    response = geo.create_coveragestore(layer_name=layer, path=geotiff_path, workspace='DRZ')
    logger.info(response, flush=True)
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
