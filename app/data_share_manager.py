import json
import uuid
import requests
class DataShareManager:
    def __init__(self, iais_url, iais_username, iais_password):
        self.iais_username = iais_username
        self.iais_password = iais_password
        self.iais_url = iais_url

    def update_iais_connection(self, iais_url, iais_username, iais_password):
        self.iais_url = iais_url
        self.iais_username = iais_username
        self.iais_password = iais_password

        #check if url starts wirh https://
        if not self.iais_url.startswith('https://'):
            #make sure it does not start with http://
            if self.iais_url.startswith('http://'):
                self.iais_url = self.iais_url.replace('http://', '')
            else:
                self.iais_url = 'https://' + self.iais_url

        #check if url ends with /, if so remove it
        if not self.iais_url.endswith('/'):
            self.iais_url = self.iais_url + '/'

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