import multiprocessing
import os
import os.path as path
import json

import psutil
import requests
import time
import cv2
import zipfile
from functools import partial


class WebodmManager():
    def __init__(self, address="127.0.0.1", internal_port="8000", public_port="8000", username="admin", password="admin"):
        self.address = address
        self.port = internal_port
        self.public_port = public_port
        self.username = username
        self.password = password
        self.url = "http://{}:{}".format(address, internal_port)


    @staticmethod
    def scale_image(size, path):
        img = cv2.imread(os.path.abspath(path))
        # print("Scaling image", os.path.abspath(path))
        # print("Image size", img.shape)
        scale_percent = size / img.shape[1]
        dim = (int(img.shape[1] * scale_percent), int(img.shape[0] * scale_percent))
        resized = cv2.resize(img, dim, interpolation=cv2.INTER_NEAREST)
        img = None
        scaled_image_path = os.path.join(os.path.dirname(path), 'proxy', os.path.basename(path))
        cv2.imwrite(scaled_image_path, resized)
        resized = None
        os.system('exiftool -TagsFromFile ' + path + ' ' + scaled_image_path)
        return scaled_image_path

    def authenticate(self):
        try_count = 0
        while try_count < 20:
            try:
                response = requests.post('{}/api/token-auth/'.format(self.url),
                                data={'username': self.username, 'password': self.password})
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

    def project_exists(self, token, wo_project_id):
        response = requests.get('{}/api/projects/{}/'.format(self.url, wo_project_id),
                                    headers={'Authorization': 'JWT {}'.format(token)}).json()
        if response:
            return True
        return False

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

    def upload_and_process_images(self, token, wo_project_id, filenames, fast_orthophoto=False):
        files = []

        for filename in filenames:
            _, ext = os.path.splitext(filename)
            ext = ext[1:].lower()
            # Prepare the files dictionary for the current image
            file = ('images', (os.path.basename(filename), open(filename, 'rb'), 'image/{}'.format(ext)))
            files.append(file)

        human_readable_time_date = time.strftime("%Y-%m-%d_%H-%M-%S", time.localtime())

        if fast_orthophoto:
            name = "Fast-Model_" + human_readable_time_date
            options = json.dumps([
                {'name': "auto-boundary", 'value': True},
                {'name': "fast-orthophoto", 'value': True},
            ])
        else:
            name = "Full-3D-Model_" + human_readable_time_date
            options = json.dumps([
                {'name': "orthophoto-resolution", 'value': 24},
            ])


        response = requests.post('{}/api/projects/{}/tasks/'.format(self.url, wo_project_id),
                            headers={'Authorization': 'JWT {}'.format(token)},
                            files=files,
                            data={
                                'name': name,
                                'options': options
                            }).json()


        return response

    def get_all_tasks(self, token, wo_project_id):
        response = requests.get('{}/api/projects/{}/tasks/'.format(self.url, wo_project_id),
                            headers={'Authorization': 'JWT {}'.format(token)
                            }).json()
        response = sorted(response, key=lambda k: k['created_at'])
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

    def get_task_data_by_key(self, token, wo_project_id, task_id, key):
        task = requests.get('{}/api/projects/{}/tasks/{}/'.format(self.url, wo_project_id, task_id),
                                headers={'Authorization': 'JWT {}'.format(token)
                                         }).json()
        # print(task, flush=True)
        return task[key]

    def get_assets_from_task(self, token, wo_project_id, task_id, asset="all.zip"):
        response = requests.get('{}/api/projects/{}/tasks/{}/download/{}'.format(self.url, wo_project_id, task_id, asset),
                            headers={'Authorization': 'JWT {}'.format(token)})
        if response.status_code == 200:
            return response
        else:
            print("Error getting assets from task: " + str(response.status_code))
            return None

    def download_assets_from_task(self, token, wo_project_id, task_id, destination, asset="all.zip"):
        response = requests.get('{}/api/projects/{}/tasks/{}/download/{}'.format(self.url, wo_project_id, task_id, asset),
                                headers={'Authorization': 'JWT {}'.format(token)})
        if response.status_code == 200:
            print("Downloading assets from task", flush=True)
            #save file
            save_path = path.join(destination, asset)
            with open(save_path, 'wb') as f:
                f.write(response.content)

            #if zip, extract
            if asset.endswith(".zip"):
                #create folder
                destination = path.join(destination, asset[:-4])
                #extract
                with zipfile.ZipFile(save_path, 'r') as zip_ref:
                    zip_ref.extractall(destination)
                os.remove(save_path)

            return destination
        else:
            print("Error getting assets from task: " + str(response.status_code), flush=True)
            return None


    def scale_images(self, image_paths, image_size):
        proxy_path = os.path.join(os.path.dirname(image_paths[0]), 'proxy')
        if not os.path.exists(proxy_path):
            os.mkdir(proxy_path)

        print("Scaling images", image_paths)
        scaled_image_paths = []
        nmbr_of_processes = self.calculate_number_of_safely_usable_processes(image_paths[0])
        print('number of processes: ', nmbr_of_processes)
        if nmbr_of_processes < len(image_paths):
            nmbr_of_processes = len(image_paths)
        pool = multiprocessing.Pool(nmbr_of_processes)
        func = partial(WebodmManager.scale_image, image_size)
        scaled_image_paths = pool.map(func, image_paths)
        pool.close()
        pool.join()
        print("scaling done")
        return scaled_image_paths

    def get_image_memory_usage(self, image_path):
        # Get memory usage before loading the image
        initial_memory = psutil.virtual_memory().used

        # Load the image
        loaded_image = cv2.imread(image_path)

        # Get memory usage after loading the image
        final_memory = psutil.virtual_memory().used

        # Calculate the memory used by the loaded image
        image_memory_usage = final_memory - initial_memory

        # Release the memory occupied by the loaded image
        loaded_image = None

        return image_memory_usage

    def calculate_number_of_safely_usable_processes(self, example_image_path):
        example_memory_usage = self.get_image_memory_usage(example_image_path)
        print('example_memory_usage: ', example_memory_usage, 'of image: ', example_image_path)
        available_memory = psutil.virtual_memory().available

        # Calculate the number of processes based on memory usage
        max_processes = multiprocessing.cpu_count()
        if max_processes > 8:
            max_processes = max_processes - 2
        #len(os.sched_getaffinity(0))
        safely_usable_processes = min(max_processes, int(available_memory / example_memory_usage))
        print('safely_usable_processes: ', safely_usable_processes, 'with max_processes: ', max_processes, 'and available_memory: ', available_memory)
        return safely_usable_processes

    def clean_up(self, image_paths):
        if not image_paths:
            return
        if len(image_paths) == 0:
            return

        for filename in image_paths:
            try:
                if os.path.isfile(filename) or os.path.islink(filename):
                    os.unlink(filename)
                elif os.path.isdir(filename):
                    print("Directory found", filename)
            except Exception as e:
                print('Failed to delete %s. Reason: %s' % (filename, e))

        proxy_folder = os.path.dirname(image_paths[0])
        if proxy_folder.endswith('proxy'):
            files = os.listdir(proxy_folder)
            for file in files:
                file_path = os.path.join(proxy_folder, file)
                try:
                    if os.path.isfile(file_path) or os.path.islink(file_path):
                        os.unlink(file_path)
                    elif os.path.isdir(file_path):
                        print("Directory found", file_path)
                except Exception as e:
                    print('Failed to delete %s. Reason: %s' % (file_path, e))
            os.rmdir(proxy_folder)
