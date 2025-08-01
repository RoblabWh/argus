import time
import requests

class WebodmManager():
    def __init__(self, active, url, username="admin", password="admin"):
        self.active = active
        self.url = url
        self.username = username
        self.password = password

        if self.active:
             self.authentication = self.authenticate()
        
    
    def authenticate(self):
        try_count = 0
        while try_count < 5:
            try:
                data={'username': self.username, 'password': self.password}
                response = requests.post('{}/api/token-auth/'.format(self.url),
                                data=data,
                                headers={'Content-Type': 'application/x-www-form-urlencoded'})
                if response.status_code == 200:
                    return response.json()['token']
            except requests.exceptions.ConnectionError:
                pass
            try_count += 1
            time.sleep(1)

        if try_count == 5:
            print('Failed to connect to WebODM Server "{}", timeout exceeded'.format(self.url))
        else:
            print('Failed to connect to WebODM Server "{}", with http status code {}'.format(self.url, response.status_code))
        return None
    
    def check_connection(self):
        if not self.active:
            return False
        if not self.authentication:
            self.authentication = self.authenticate()
        return self.authentication is not None and self.authentication != ""
    
    def get_all_projects(self):
        if not self.check_connection():
            return None
        try:
            response = requests.get(f"{self.url}/api/projects/",
                                    headers={'Authorization': 'JWT {}'.format(self.authentication)})
            print(response)
            if response.status_code == 200:
                return response.json()
            else:
                print(f"Failed to fetch projects: {response.status_code} - {response.text}")
                return None
        except requests.exceptions.RequestException as e:
            print(f"Error fetching projects: {e}")
            return None
    
    def check_project_exists(self, project_id):
        if not self.check_connection():
            return False
        try:
            response = requests.get(f"{self.url}/api/projects/{project_id}/",
                                    headers={'Authorization': f'Token {self.authentication}'})
            return response.status_code == 200
        except requests.exceptions.RequestException as e:
            print(f"Error checking project existence: {e}")
            return False