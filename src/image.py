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

import cv2
import imutils

from exif_header import ExifHeader

class Image:
    def __init__(self, image_path):
        """
        Constructor
        :param image_path: image path
        """
        self.image_path = image_path
        self.exif_header = ExifHeader(image_path)
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
            return cv2.cvtColor(cv2.imread(self.image_path,cv2.IMREAD_UNCHANGED),cv2.COLOR_BGR2BGRA)
        else:
            return self.matrix

    def set_matrix(self, matrix):
        self.matrix = matrix
        if matrix is not None:
            self.width = matrix.shape[1]
            self.height = matrix.shape[0]

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
        matrix = self.get_matrix()
        scale_factor = 300 / matrix.shape[1]
        new_size = (300, int(matrix.shape[0] * scale_factor))
        thumbnail = cv2.resize(matrix, new_size, interpolation=cv2.INTER_NEAREST)

        #check if sub-folder 'thumbnails' exists
        if not os.path.exists(os.path.join(os.path.dirname(self.image_path), 'thumbnails')):
            os.makedirs(os.path.join(os.path.dirname(self.image_path), 'thumbnails'))

        path = os.path.join(os.path.dirname(self.image_path), 'thumbnails', os.path.basename(self.image_path))
        cv2.imwrite(path, thumbnail)
        self.matrix = None


    @staticmethod
    def resize_image(matrix, width, height):
        return cv2.resize(matrix, (width, height), cv2.INTER_NEAREST)

    @staticmethod
    def rotate_image(matrix, rotate_angle_degree):
        return imutils.rotate_bound(matrix, rotate_angle_degree) 
