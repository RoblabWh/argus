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

    def get_all_pois_from_iais(self):
        response = requests.get(self.iais_url + '/poi', auth=(self.iais_username, self.iais_password))
        print(response, flush=True)
        return response.json()

    def send_poi_to_iais(self, poi_data):
        id = self.generate_uuid()
        name = poi_data['name']
        type = poi_data['type']
        description = poi_data['description']
        latitude = poi_data['latitude']
        longitude = poi_data['longitude']
        wkt = "POINT(" + str(longitude) + " " + str(latitude) + ")"
        epsg = "4326"
        data = {'id': id,
                'name': name,
                'type': type,
                'description': description,
                'wkt': wkt,
                'epsg': epsg
                }

        response = requests.put(self.iais_url + '/poi', json=data, auth=(self.iais_username, self.iais_password))
        print(response, flush=True)
        return response.status_code

    def generate_uuid(self):
        return str(uuid.uuid4())