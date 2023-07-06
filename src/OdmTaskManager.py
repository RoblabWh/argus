# OdmTaskManager for generating ortho photo in python (non-blocking)
# Use:
# docker run -ti -p 3000:3000 opendronemap/nodeodm
# to start the node
# kill with
# docker kill $(docker ps -q)
# docker rm $(docker ps -a -q)

# Installation: pip install pyodm

import os
from pyodm import Node
from pyodm.types import TaskStatus
from pathlib import Path
import re
import multiprocessing
from functools import partial
import time
import docker
import cv2

import socket

from itertools import repeat





class OdmTaskManager:

    _image_size = 960

    def __init__(self, path_to_image_folder, port=3000):
        """
        :param image_paths: List of Strings of Paths to input_images
        :param inputfolder: If image_paths are not provided search images in folder
        """
        self.path_to_image_folder = path_to_image_folder
        self.address ='127.0.0.1'
        DOCKER_ENV_KEY = os.environ.get('AM_I_IN_A_DOCKER_CONTAINER', False)
        if DOCKER_ENV_KEY:
            # self.address = '172.17.0.1'
            self.address = 'host.docker.internal'
            print('using different ip to access localhost/ 127.0.0.1 because of running in a docker container, now using:', self.address)


        print("Establish client from environment variables")
        self.client = docker.from_env()
        print("Create container")
        self.container = self.client.containers.run("opendronemap/nodeodm", stdin_open=True, tty=True,
                                                    ports={"3000": port}, detach=True)
        # professional (and now very cool) way to wait for container to be ready
        time.sleep(6)

        self.check_connection(self.address, port)

        self.node = Node(self.address, port)
        self.task = None
        self.task_complete = False
        self.console_output = []

    @staticmethod
    def scale_image(size, path):
        img = cv2.imread(os.path.abspath(path))
        # print("Scaling image", os.path.abspath(path))
        # print("Image size", img.shape)
        scale_percent = size / img.shape[1]
        dim = (int(img.shape[1] * scale_percent), int(img.shape[0] * scale_percent))
        resized = cv2.resize(img, dim, interpolation=cv2.INTER_NEAREST)
        scaled_image_path = os.path.dirname(path) + '/proxy/' + os.path.basename(path)
        cv2.imwrite(scaled_image_path, resized)
        os.system('exiftool -TagsFromFile ' + path + ' ' + scaled_image_path)
        return scaled_image_path

    # def get_host_ip(self):
    #     client = docker.from_env()
    #     host_ip = client.containers.get('hostname').attrs['NetworkSettings']['IPAddress']
    #     return host_ip

    def ping_address(self, address):
        response = os.system("ping -c 1 " + address)
        if response == 0:
            pingstatus = "Network Active"
        else:
            pingstatus = "Network Error"
        return pingstatus

    def check_connection(self, host, port, timeout=2):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)  # presumably
        sock.settimeout(timeout)
        try:
            sock.connect((host, port))
        except:
            print('ODM CONTAINER no connection')
        else:
            sock.close()
            print('ODM CONTAINER connection successful')

    def set_images_scaled(self, image_paths, scaled_image_size=960):
        self._image_size = scaled_image_size
        self.set_images(self.scale_images(image_paths))

    def set_images(self, image_paths):
        self.image_paths = image_paths

    def scale_images(self, image_paths):
        self.image_paths = image_paths

        if not os.path.exists(self.path_to_image_folder + 'rgb/proxy/'):
            os.mkdir(self.path_to_image_folder + 'rgb/proxy/')
        if os.path.exists(self.path_to_image_folder + 'ir/'):
            if not os.path.exists(self.path_to_image_folder + 'ir/proxy/'):
                os.mkdir(self.path_to_image_folder + 'ir/proxy/')


        print("Scaling images", image_paths)
        scaled_image_paths = []
        nmbr_of_processes = len(os.sched_getaffinity(0))  # 6
        print('number of processes: ', nmbr_of_processes)
        if nmbr_of_processes < len(image_paths):
            nmbr_of_processes = len(image_paths)
        pool = multiprocessing.Pool(nmbr_of_processes)
        func = partial(OdmTaskManager.scale_image, self._image_size)
        scaled_image_paths = pool.map(func, self.image_paths)
        #scaled_image_paths = pool.map(OdmTaskManager.scale_image, zip(self.image_paths, len(self.image_paths) * [self._image_size]))
        pool.close()
        pool.join()
        print("scaling done")
        return scaled_image_paths

    def run_task(self, options={'feature-quality': 'medium', 'fast-orthophoto': True, 'auto-boundary': True, 'pc-ept': True,'cog': True}):
        """
        :param options: Dictionary with ODM flags
        """
        self.task = self.node.create_task(self.image_paths, options)
        print(self.task.info())
        # self.task.wait_for_completion(status_callback=self.console_out, interval=5)
        # self.task.download_assets('results')
        #feature-quality medium --fast-orthophoto --auto-boundary --pc-ept --cog --project-path /var/www/data 6349880b-4228-4218-87a7-ff63b4ec2fef
        #--feature-quality medium --fast-orthophoto --auto-boundary --pc-ept --cog --project-path /var/www/data 94708928-3b8f-48c0-8336-68f97f951f14
        #options={'auto-boundary': True, 'dsm': False, 'fast-orthophoto': True,'feature-quality': 'lowest'}


    def get_image_paths(self, path):
        """
        :param path: Inputpath to yield images from. No subdirectories included
        """
        inputfolder = str(path)
        for root, dirs, files in os.walk(path):
            for file in files:
                basename = os.path.basename(file).lower()
                ext = os.path.splitext(basename)[-1].lower()
                basename = basename.replace(ext, '')
                if ext in ['.jpg'] and bool(re.compile('^d').match(basename)):
                    if root == inputfolder:
                        yield Path(os.path.join(root, file))

    def console_out(self, task_info):
        for item in self.task.output(-200):
            if item not in self.console_output:
                print(item)
                self.console_output.append(item)

    def task_running(self):
        case = self.task.info().status
        if case == TaskStatus.RUNNING:
            #self.console_out(None)
            return True
        elif case == TaskStatus.FAILED:
            print("Task has failed for some reason. Check console output for information")
            self.clean_up()
            return False
        elif case == TaskStatus.CANCELED:
            print("Task was cancelled by user. What are you doing?!")
            self.clean_up()
            return False
        elif case == TaskStatus.COMPLETED:
            print("Task completed")
            self.task.download_assets('results')
            self.task_complete = True
            self.clean_up()
            return False
        else:
            print("not defined case in OdmTaskManager.check_task()")
            return False

    def clean_up(self):
        self.task.remove()

        folder = self.path_to_image_folder + 'proxy'

        if os.path.exists(folder):
            for filename in os.listdir(folder):
                file_path = os.path.join(folder, filename)
                try:
                    if os.path.isfile(file_path) or os.path.islink(file_path):
                        os.unlink(file_path)
                    elif os.path.isdir(file_path):
                        print("Directory found", file_path)
                except Exception as e:
                    print('Failed to delete %s. Reason: %s' % (file_path, e))

    def close(self):
        self.container.stop()
        self.container.remove()






