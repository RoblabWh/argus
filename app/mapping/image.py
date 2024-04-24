#!/usr/bin/env python3
__author__      = "Artur Leinweber"
__copyright__ = "Copyright 2020"
__credits__ = ["None"]
__license__ = "GPL"
__version__ = "1.0.1"
__maintainer__ = "Artur Leinweber"
__email__ = "arturleinweber@live.de"
__status__ = "Production"

import os
import shutil

import cv2
import imutils
import numpy as np

from .exif_header import ExifHeader
from thermal.thermal_analyser import ThermalAnalyser

class Image:
    def __init__(self, image_path):
        """
        Constructor
        :param image_path: image path
        """
        self.image_path = image_path
        self.exif_header = ExifHeader(image_path)
        if self.exif_header.ir:
            self.move_to_super_folder('ir')
        elif self.exif_header.pano:
            self.move_to_super_folder('panos')
        else:
            self.move_to_super_folder('rgb')

        (self.width, self.height) = self.exif_header.get_image_size()
        self.matrix = None
        self.rgb_counterpart_path = None
        
    def update_path(self, path):
        self.image_path = path
        self.exif_header.update_path(path)

    def set_rgb_counterpart_path(self, path):
        self.rgb_counterpart_path = path

    def get_rgb_counterpart_path(self):
        """
        Return path of RGB counterpart if image is infrared
        :return: string
        """
        return self.rgb_counterpart_path

    def set_to_ir(self):
        self.exif_header.enable_ir()

    def get_image_path(self):
        """
        Return image path
        :return: string
        """
        return self.image_path

    def get_exif_header(self):
        """
        Return EXIF header of image 
        :return: ExifHeader
        """
        return self.exif_header

    def get_matrix(self):
        """
        Return image matrix
        :return: OpenCV Mat
        """
    
        if self.matrix is None:
            if self.exif_header.ir:
                try:
                    report_id = self.image_path.split('/')[-2]
                    image = ThermalAnalyser(None).get_image_temp_matrix(report_id, self.image_path)
                    image = np.expand_dims(image, axis=2)
                    image = np.concatenate((image, np.ones((image.shape[0], image.shape[1], 1), dtype=np.float32)), axis=2)

                except Exception as e:
                    print("loading thermal data failed with error: ", e)
                    image = cv2.cvtColor(cv2.imread(self.image_path,cv2.IMREAD_UNCHANGED),cv2.COLOR_BGR2BGRA)
                return image
            else:
                return cv2.cvtColor(cv2.imread(self.image_path,cv2.IMREAD_UNCHANGED),cv2.COLOR_BGR2BGRA)
        else:
            return self.matrix

    def set_matrix(self, matrix):
        self.matrix = matrix

    def get_width(self):
        """
        Return width of image matrix
        :return: int
        """
        
        return self.width

    def get_height(self):
        """
        Return height of image matrix
        :return: int
        """
        return self.height

    def generate_thumbnail(self):
        """
        Generate thumbnail of image and save it in a sub-folder in the same directory called 'thumbnails'

        """
        matrix = cv2.cvtColor(cv2.imread(self.image_path,cv2.IMREAD_UNCHANGED),cv2.COLOR_BGR2BGRA)
        scale_factor = 350 / matrix.shape[1]
        new_size = (350, int(matrix.shape[0] * scale_factor))
        thumbnail = cv2.resize(matrix, new_size, interpolation=cv2.INTER_NEAREST)

        #check if sub-folder 'thumbnails' exists
        if not os.path.exists(os.path.join(os.path.dirname(self.image_path), 'thumbnails')):
            os.makedirs(os.path.join(os.path.dirname(self.image_path), 'thumbnails'))

        path = os.path.join(os.path.dirname(self.image_path), 'thumbnails', os.path.basename(self.image_path))
        cv2.imwrite(path, thumbnail)
        matrix = None


    @staticmethod
    def resize_image(matrix, width, height):
        return cv2.resize(matrix, (width, height), cv2.INTER_NEAREST)

    @staticmethod
    def rotate_image(matrix, rotate_angle_degree):
        return imutils.rotate_bound(matrix, rotate_angle_degree)

    def move_to_super_folder(self, subfolder):
        last_folder = os.path.basename(os.path.dirname(self.image_path))
        if last_folder != subfolder:
            subfolder_path = os.path.join(os.path.dirname(self.image_path), subfolder)
            image_path = os.path.join(subfolder_path, os.path.basename(self.image_path))
            if not os.path.exists(subfolder_path):
                os.makedirs(subfolder_path)
            shutil.move(self.image_path, image_path)
            self.update_path(image_path)
