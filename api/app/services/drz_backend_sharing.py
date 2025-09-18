import datetime as dt
import json
import requests

iais_url = "http://iais-backend:8000/api/"

def send_geojson_poi_to_iais(poi_data):

    geometry = poi_data['geometry']

    type = poi_data['properties']['type']
    subtype = poi_data['properties']['subtype']
    danger_level = False #poi_data['properties']['danger_level']
    detection = poi_data['properties']['detection']
    name = poi_data['properties']['name']
    description = poi_data['properties']['description']
    datetime = poi_data['properties']['datetime']
    #convert datetime from 03.08.2024 10:00 to 2024-03-08T10:00:00
    datetime = dt.datetime.strptime(datetime, '%d.%m.%Y %H:%M').isoformat()

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
    response = requests.put(url, headers=headers, data=json.dumps(data)  )#, auth=(self.iais_username, self.iais_password))

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