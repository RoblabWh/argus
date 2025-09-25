import time
import requests
import os
import json
from app.config import config

import logging
logger = logging.getLogger(__name__)


class WebodmManager:
    def __init__(
        self,
        active=config.WEBODM_ENABLED,
        url=config.WEBODM_URL,
        username=config.WEBODM_USERNAME,
        password=config.WEBODM_PASSWORD,
    ):
        self.active = active
        self.url = url
        self.username = username
        self.password = password

        if self.active:
            self.authentication = self.authenticate()

    def authenticate(self):
        self.password = config.WEBODM_PASSWORD
        self.username = config.WEBODM_USERNAME
        self.url = config.WEBODM_URL
        try_count = 0
        while try_count < 5:
            try:
                data = {"username": self.username, "password": self.password}
                response = requests.post(
                    "{}/api/token-auth/".format(self.url),
                    data=data,
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )
                if response.status_code == 200:
                    return response.json()["token"]
            except requests.exceptions.ConnectionError:
                logger.error(f"Connection error when connecting to WebODM at {self.url}, retrying...")
            try_count += 1
            time.sleep(1)

        if try_count == 5:
            logger.error(
                'Failed to connect to WebODM Server "{}", timeout exceeded'.format(
                    self.url
                )
            )
        else:
            logger.warning(
                'Failed to connect to WebODM Server "{}", with http status code {}'.format(
                    self.url, response.status_code
                )
            )
        return None

    def check_connection(self):
        if not self.active:
            return False
        if not self.authentication:
            self.authentication = self.authenticate()
        
        tries = 0
        while tries < 2 and (self.authentication is not None and self.authentication != ""):
            try:
                response = requests.get(
                    f"{self.url}/api/projects/",
                    headers={"Authorization": "JWT {}".format(self.authentication)},
                )
                if response.status_code == 200:
                    return True
                else:
                    logger.warning(f"WebODM connection check failed with status code {response.status_code} in {tries+1}. try")
                    if tries == 0:
                        self.authentication = self.authenticate()
                    else:
                        return False
            except requests.exceptions.RequestException as e:
                self.authentication = self.authenticate()
            tries += 1
        
        return False

    def get_all_projects(self):
        if not self.check_connection():
            return None
        try:
            response = requests.get(
                f"{self.url}/api/projects/",
                headers={"Authorization": "JWT {}".format(self.authentication)},
            )
            print(response)
            if response.status_code == 200:
                return response.json()
            else:
                print(
                    f"Failed to fetch projects: {response.status_code} - {response.text}"
                )
                return None
        except requests.exceptions.RequestException as e:
            print(f"Error fetching projects: {e}")
            return None

    def check_project_exists(self, project_id):
        if not self.check_connection():
            return False
        try:
            response = requests.get(
                f"{self.url}/api/projects/{project_id}/",
                headers={"Authorization": "JWT {}".format(self.authentication)},
            )
            return response.status_code == 200
        except requests.exceptions.RequestException as e:
            print(f"Error checking project existence: {e}")
            return False

    def create_project(self, name, description):
        if not self.check_connection():
            return None
        response = requests.post(
            "{}/api/projects/".format(self.url),
            headers={"Authorization": "JWT {}".format(self.authentication)},
            data={"name": name, "description": description},
        )

        if response.status_code == 201:
            print('Project "{}" created successfully'.format(name))
            return response.json()["id"]
        else:
            print('Error creating project "{}"'.format(name))
            print(response.text)

    def get_project(self, id):
        if not self.check_connection():
            return None
        response = requests.get(
            "{}/api/projects/{}/".format(self.url, id),
            headers={"Authorization": "JWT {}".format(self.authentication)},
        )
        if response.status_code == 200:
            return response.json()
        else:
            print('Error fetching project "{}"'.format(id))
            print(response.text)
            return None

    def upload_and_process_images(
        self, project_id, images, odm_full=False, image_type="color"
    ):
        logger.info(f"Uploading and processing images for project {project_id} with odm_full={odm_full} and image_type={image_type}")
        logger.info(f"uploading a total of {len(images)} images, with first image {images[0] if images else 'None'}")

        files = []

        for image in images:
            path = image
            _, ext = os.path.splitext(path)
            ext = ext[1:].lower()
            # Prepare the files for upload over HTTP request
            file = (
                "images",
                (os.path.basename(path), open(path, "rb"), "image/{}".format(ext)),
            )
            files.append(file)

        human_readable_time_date = time.strftime("%m-%d_%H:%M", time.localtime())

        if odm_full:
            name = f"Full_3D-Model_{image_type}_{human_readable_time_date}"
            options = json.dumps(
                [
                    {"name": "orthophoto-resolution", "value": 24},
                ]
            )
        else:
            name = f"Fast_ODM_map_{image_type}_{human_readable_time_date}"
            options = json.dumps(
                [
                    {"name": "auto-boundary", "value": True},
                    {"name": "fast-orthophoto", "value": True},
                ]
            )

        response = requests.post(
            "{}/api/projects/{}/tasks/".format(self.url, project_id),
            headers={"Authorization": "JWT {}".format(self.authentication)},
            files=files,
            data={"name": name, "options": options},
        ).json()
        print(f"Created task {name} with options {options} for project {project_id}")
        return response.get("id")

    def get_task(self, project_id, task_id):
        if not self.check_connection():
            return None
        response = requests.get(
            "{}/api/projects/{}/tasks/{}/".format(self.url, project_id, task_id),
            headers={"Authorization": "JWT {}".format(self.authentication)},
        )
        if response.status_code == 200:
            return response.json()
        else:
            print(
                'Error fetching task "{}" in project "{}"'.format(task_id, project_id)
            )
            print(response.text)
            return None

    def download_results(self, project_id, task_id):
        if not self.check_connection():
            return None
        response = requests.get(
            "{}/api/projects/{}/tasks/{}/download/".format(
                self.url, project_id, task_id
            ),
            headers={"Authorization": "JWT {}".format(self.authentication)},
        )
        if response.status_code == 200:
            return response.content
        else:
            print(
                'Error downloading results for task "{}" in project "{}"'.format(
                    task_id, project_id
                )
            )
            print(response.text)
            return None

    def download_orthophoto(self, project_id, task_id, report_id):
        if not self.check_connection():
            return None

        path = config.UPLOAD_DIR / f"{report_id}/ODM-{task_id}orthophoto.tif"

        response = requests.get(
            "{}/api/projects/{}/tasks/{}/download/orthophoto.tif".format(
                self.url, project_id, task_id
            ),
            headers={"Authorization": "JWT {}".format(self.authentication)},
            stream=True,
        )
        with open(path, "wb") as f:
            for chunk in response.iter_content(chunk_size=1024):
                if chunk:
                    f.write(chunk)
        logger.info(f"Saved {path}")
        return path

    def get_project_tasks(self, project_id):
        project = self.get_project(project_id)
        if not project:
            return None
        tasks = project.get("tasks", [])
        if not tasks:
            print(f"No tasks found for project {project_id}")
            return None
        tasks_data = []
        for task in tasks:
            task_id = task
            if not task_id:
                print(f"Task ID not found for task {task}")
                continue
            task_details = self.get_task(project_id, task_id)
            url_to_task = f"{self.url}/dashboard/?project_task_open={project_id}&project_task_expanded={task_id}"
            if task_details['status'] == 40:
                url_to_task = f"{self.url}/map/project/{project_id}/task/{task_id}/"
            task_details["url_to_task"] = url_to_task
            
            if not task_details:
                print(f"Failed to fetch details for task {task_id}")
                continue
            tasks_data.append(task_details)
        return tasks_data
