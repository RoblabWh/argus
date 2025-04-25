import json
import uuid
import requests
import datetime as dt
import os
from geo.Geoserver import Geoserver

class DataShareManager:
    def __init__(self, iais_url, iais_username, iais_password, geo_server_base_url='http://10.26.2.42:8080/geoserver'):
        self.update_iais_connection(iais_url, iais_username, iais_password)
        self.update_geo_server_connection(geo_server_base_url)

    def update_iais_connection(self, iais_url, iais_username, iais_password):
        self.update_backend_url(iais_url)
        self.iais_username = iais_username
        self.iais_password = iais_password


    def update_geo_server_connection(self, geo_server_base_url):
        self.geo_server_base_url = geo_server_base_url
        try:
            print(f"Connecting to geoserver at {self.geo_server_base_url}", flush=True)
            self.geo = Geoserver(self.geo_server_base_url)#, username=geo_server_username, password=geo_server_password)
            print(f"Connected to geoserver at {self.geo_server_base_url}", flush=True)
        except Exception as e:
            print(f"Error while connecting to geoserver: {e}", flush=True)
            self.geo = None

    def get_geo_server_connection(self):
        if self.geo_server_base_url:
            return self.geo_server_base_url
        return ""


    def update_backend_url(self, backend_url):
        # check if url starts wirh https://
        if not backend_url.startswith('https://') and not backend_url.startswith('http://'):
            backend_url = 'https://' + backend_url

        if not backend_url.endswith('/'):
            backend_url = backend_url + '/'

        self.iais_url = backend_url

    def get_all_pois_from_iais(self):

        url = self.iais_url + 'poi/'
        params = {
            "limit": 100
        }
        headers = {
            "accept": "application/json"
        }

        response = requests.get(url, params=params, headers=headers) #auth=(self.iais_username, self.iais_password))
        if response.status_code == 200:
            print("GET request successful!", flush=True)
        else:
            print(f"GET request failed with status code {response.status_code}", flush=True)

        return response.json()

    def send_poi_to_iais(self, poi_data):
        id = str(self.generate_uuid())
        name = poi_data['name']
        type = poi_data['type']
        description = poi_data['description']
        latitude = poi_data['latitude']
        longitude = poi_data['longitude']
        wkt = "POINT(" + str(longitude) + " " + str(latitude) + ")"
        epsg = 4326

        url = self.iais_url + 'poi/'

        headers = {
            "accept": "*/*",
            "Content-Type": "application/json"
        }

        data = {'id': id,
                'name': name,
                'type': type,
                'description': description,
                'wkt': wkt,
                'epsg': epsg
        }

        print(url, headers, json.dumps(data), flush=True)
        response = requests.put(url, headers=headers, data=json.dumps(data))#, auth=(self.iais_username, self.iais_password))

        if response.status_code == 200:
            return "PUT request successful!"
        else:
            print(f"PUT request failed with status code {response.status_code}", flush=True)
            return requests.json()

    def send_geojson_poi_to_iais(self, poi_data):

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

        url = self.iais_url + 'poi/'
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



    def remove_poi_from_iais(self, poi_id):
        url = self.iais_url + 'poi/'
        params = {
            "id": str(poi_id)
        }
        headers = {
            "accept": "*/*"
        }

        response = requests.delete(url, params=params, headers=headers)

        if response.status_code == 200:
            return "DELETE request successful!"
        else:
            print(f"DELETE request failed with status code {response.status_code}", flush=True)
            return "DELETE request failed!"

    def generate_uuid(self):
        return str(uuid.uuid4())

    def send_map_to_iais(self, maps, report_id):
        message = "Sending maps to iais"
        for map_data in maps:
            file_path = map_data['file'].replace('png', 'tif')
            #test if file exists
            if not os.path.exists(file_path):
                print(f"File {file_path} does not exist", flush=True)
                message += f"\nFile {file_path} does not exist"
                continue
            else:
                print(f"File {file_path} exists", flush=True)

            #send file to iais
            print("Sending file to iais", flush=True)

            try:
                filename = os.path.basename(file_path)
                response = self.geo.create_coveragestore(layer_name=f"argus_{report_id}_{filename}", path=file_path, workspace='DRZ')
                print(response, flush=True)
            except Exception as e:
                print(f"Error while sending file to iais: {e}", flush=True)
                message += f"\nError while sending file to iais: {e}"
        return message