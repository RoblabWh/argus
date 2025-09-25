import datetime as dt
import json
import requests

#iais_url = "http://iais-backend:8000/api/"
iais_url = "https://fake-rlw.rettungsrobotik.de/"
iais_url = "https://eve.iais.fraunhofer.de/"
import logging
logger = logging.getLogger(__name__)

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




# def send_map_to_iais( maps, report_id):
#     message = "Sending maps to iais"
#     for map_data in maps:
#         file_path = map_data['file'].replace('png', 'tif')
#         #test if file exists
#         if not os.path.exists(file_path):
#             print(f"File {file_path} does not exist", flush=True)
#             message += f"\nFile {file_path} does not exist"
#             continue
#         else:
#             print(f"File {file_path} exists", flush=True)

#         #send file to iais
#         print("Sending file to iais", flush=True)

#         try:
#             filename = os.path.basename(file_path)
#             response = self.geo.create_coveragestore(layer_name=f"argus_{report_id}_{filename}", path=file_path, workspace='DRZ')
#             print(response, flush=True)
#         except Exception as e:
#             print(f"Error while sending file to iais: {e}", flush=True)
#             message += f"\nError while sending file to iais: {e}"
#     return message