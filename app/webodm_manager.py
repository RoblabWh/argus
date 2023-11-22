import os
import json
import requests
import time

class WebodmManager():
    def __init__(self, address="127.0.0.1", internal_port="8000", public_port="8000", username="admin", password="admin"):
        self.address = address
        self.port = internal_port
        self.public_port = public_port
        self.username = username
        self.password = password
        self.url = "http://{}:{}".format(address, internal_port)

    def authenticate(self):
        try_count = 0
        while try_count < 20:
            try:
                response = requests.post('{}/api/token-auth/'.format(self.url),
                                data={'username': self.username, 'password': self.username})
                if response.status_code == 200:
                    return response.json()['token']
            except requests.exceptions.ConnectionError:
                pass
            try_count += 1
            time.sleep(1)

        if try_count == 10:
            print('Failed to connect to WebODM Server "{}", timeout exceeded'.format(self.url))
        else:
            print('Failed to connect to WebODM Server "{}", with http status code {}'.format(self.url, response.status_code))

    def configure_node(self, token, address, port):
        response = requests.get('{}/api/processingnodes/'.format(self.url),
                                    headers={'Authorization': 'JWT {}'.format(token)},
                                    data={'hostname': address, 'port': port}).json()
        if not response:
            response = requests.post('{}/api/processingnodes/'.format(self.url),
                                        headers={'Authorization': 'JWT {}'.format(token)},
                                        data={'hostname': address, 'port': port}).json()
        return response

    def get_project_id(self, token, name, description):
        response = requests.get('{}/api/projects/'.format(self.url),
                                                headers={'Authorization': 'JWT {}'.format(token)},
                                                data={'name': name, 'description': description}).json()

        # Workaround, because webodm ignores the data filter of get request
        for project in response:
            if project['name'] == name and project['description'] == description:
                return project['id']

    def create_project(self, token, name, description):
        response = requests.post('{}/api/projects/'.format(self.url),
                                            headers={'Authorization': 'JWT {}'.format(token)},
                                            data={'name': name, 'description': description})

        if response.status_code == 201:
            print('Project "{}" created successfully'.format(name))
            return response.json()['id']
        else:
            print('Error creating project "{}"'.format(name))
            print(response.text)

    def upload_and_process_images(self, token, wo_project_id, filenames):
        files = []

        for filename in filenames:
            _, ext = os.path.splitext(filename)
            ext = ext[1:].lower()
            # Prepare the files dictionary for the current image
            file = ('images', (os.path.basename(filename), open(filename, 'rb'), 'image/{}'.format(ext)))
            files.append(file)

        human_readable_time_date = time.strftime("Model_%Y-%m-%d_%H-%M-%S", time.localtime())

        options = json.dumps([
            {'name': "orthophoto-resolution", 'value': 24},
        ])


        response = requests.post('{}/api/projects/{}/tasks/'.format(self.url, wo_project_id),
                            headers={'Authorization': 'JWT {}'.format(token)},
                            files=files,
                            data={
                                'name': human_readable_time_date,
                                'options': options
                            }).json()
        return response

    def get_last_task_data(self, token, wo_project_id, key):
        # get all tasks
        # GET /api/projects/{project_id}/tasks/
        response = requests.get('{}/api/projects/{}/tasks/'.format(self.url, wo_project_id),
                            headers={'Authorization': 'JWT {}'.format(token)
                            }).json()

        # get last task by id
        task = response[0]
        print(task, flush=True)
        if task['status'] == 40:
            return task[key]

        return -1