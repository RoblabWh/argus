# OdmTaskManager for generating ortho photo in python (non-blocking)
# Use:
# docker run -ti -p 3000:3000 opendronemap/nodeodm
# to start the node

# Installation: pip install pyodm

import os
from pyodm import Node
from pyodm.types import TaskStatus
from pathlib import Path
import re
import time


class OdmTaskManager:

    def __init__(self, image_paths=None, inputfolder='./data'):
        """
        :param image_paths: List of Strings of Paths to input_images
        :param inputfolder: If image_paths are not provided search images in folder
        """
        if image_paths == None:
            paths = list(self.get_image_paths(inputfolder))
            self.image_paths = [str(e) for e in paths]
        else:
            self.image_paths = image_paths

        #TODO start ODM in docker
        self.node = Node('localhost', 3000)
        self.task = None
        self.task_complete = False
        self.console_output = []

    def run_task(self, options={'dsm': True, 'fast-orthophoto': True, 'feature-quality': 'lowest'}):
        """
        :param options: Dictionary with ODM flags
        """
        self.task = self.node.create_task(self.image_paths, options)
        # self.task.wait_for_completion(status_callback=self.console_out, interval=5)
        # self.task.download_assets('results')

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
            self.console_out(None)
            return True
        elif case == TaskStatus.FAILED:
            print("Task has failed for some reason. Check console output for information")
            self.task.remove()
            return False
        elif case == TaskStatus.CANCELED:
            print("Task was cancelled by user. What are you doing?!")
            self.task.remove()
            return False
        elif case == TaskStatus.COMPLETED:
            self.task.download_assets('results')
            self.task_complete = True
            self.task.remove()
            return False
        else:
            print("not defined case in OdmTaskManager.check_task()")
            return False




