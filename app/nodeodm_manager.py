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
import cv2
import psutil

import socket




class nodeodm_manager:

    _image_size = 960

    def __init__(self, address='127.0.0.1', port=3000):
        """
        :param image_paths: List of Strings of Paths to input_images
        :param inputfolder: If image_paths are not provided search images in folder
        """

        # self.check_connection(address, port)
        self.node = Node(address, port)

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
        func = partial(nodeodm_manager.scale_image, image_size)
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


    def run_task(self, image_paths, options={'feature-quality': 'medium', 'fast-orthophoto': True, 'auto-boundary': True, 'pc-ept': True,'cog': True}):
        """
        :param options: Dictionary with ODM flags
        """
        task = self.node.create_task(image_paths, options)
        print(task.info())
        return task
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

    def task_running(self, task):
        case = task.info().status
        if case == TaskStatus.RUNNING:
            return (True, False)
        elif case == TaskStatus.FAILED:
            print("Task has failed for some reason. Check console output for information", flush=True)
            return (False, False)
        elif case == TaskStatus.CANCELED:
            print("Task was cancelled by user. What are you doing?!", flush=True)
            return (False, False)
        elif case == TaskStatus.COMPLETED:
            print("Task completed", flush=True)
            task.download_assets('results')
            return (False, True)
        else:
            print("not defined case in OdmTaskManager.check_task()")
            return (False, False)

    def clean_up(self, task, image_paths):
        task.remove()

        for filename in image_paths:
            try:
                if os.path.isfile(filename) or os.path.islink(filename):
                    os.unlink(filename)
                elif os.path.isdir(filename):
                    print("Directory found", filename)
            except Exception as e:
                print('Failed to delete %s. Reason: %s' % (filename, e))
