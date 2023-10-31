import json

import requests
import os
import time
import threading

#TODO
# Erst zu WebODm weiterleiten, wenn der Prozess gestartet ist
# Automatisch anmelden
# WebODM auch beeenden wenn Programm Endet

class WebODMThread(threading.Thread):
    def __init__(self, webodm_url, images_dir, report_id, report_name, description):
        self.webodm_url = webodm_url
        self.images_dir = images_dir
        self.report_id = report_id
        self.description = description

        self.project_name = 'Report ' + str(self.report_id) + ' - '+ report_name

        self.done = False

        super().__init__()

    def run(self):
        print('Starting WebODM thread with project name: ' + self.project_name + ' and images dir: ' + self.images_dir)

        self.authenticate()

        self.list_projects()

        self.create_project()
        self.upload_images_and_process()

    def authenticate(self):
        res = requests.post('http://localhost:8000/api/token-auth/',
                            data={'username': 'argus',
                                  'password': 'argus'}).json()
        self.token = res['token']

    def list_projects(self):
        projects_response = requests.post(f'{self.webodm_url}/api/projects',
                                                headers={'Authorization': f'JWT {self.token}'})
        print(projects_response)

    def create_project(self):
        create_project_response = requests.post(f'{self.webodm_url}/api/projects/',
                                                headers={'Authorization': 'JWT {}'.format(self.token)},
                                                data={'name': self.project_name, 'description': self.description})
        print(create_project_response)

        if create_project_response.status_code == 201:
            self.project_id = create_project_response.json()['id']
            print(f'Project "{self.project_name}" created successfully')
        else:
            print('Error creating project')
            print(create_project_response.text)

    def upload_images_and_process(self):
        image_files = [f for f in os.listdir(self.images_dir) if os.path.isfile(os.path.join(self.images_dir, f))]
        images = []

        for image_file in image_files:
            image_path = os.path.join(self.images_dir, image_file)
            print(image_file)

            # Prepare the files dictionary for the current image
            file = ('images', (image_file, open(image_path, 'rb'), 'image/jpg'))
            images.append(file)

        options = json.dumps([
            {'name': "orthophoto-resolution", 'value': 24}
        ])

        res = requests.post(f'{self.webodm_url}/api/projects/{self.project_id}/tasks/',
                            headers={'Authorization': f'JWT {self.token}'},
                            files=images,
                            data={
                                'options': options
                            }).json()

        self.task_id = res['id']