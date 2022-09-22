#!/usr/bin/env python3
__author__      = "Artur Leinweber"
__copyright__ = "Copyright 2020"
__credits__ = ["None"]
__license__ = "GPL"
__version__ = "1.0.1"
__maintainer__ = "Artur Leinweber"
__email__ = "arturleinweber@live.de"
__status__ = "Production"

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
        
    def update_path(self, path):
        self.image_path = path

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

    @staticmethod
    def resize_image(matrix, width, height):
        return cv2.resize(matrix, (width, height), cv2.INTER_NEAREST)

    @staticmethod
    def rotate_image(matrix, rotate_angle_degree):
        return imutils.rotate_bound(matrix, rotate_angle_degree) 
