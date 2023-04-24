#!/usr/bin/env python3
__author__      = "Artur Leinweber"
__copyright__ = "Copyright 2020"
__credits__ = ["None"]
__license__ = "GPL"
__version__ = "1.0.1"
__maintainer__ = "Artur Leinweber"
__email__ = "arturleinweber@live.de"
__status__ = "Production"

from image import Image
from rectangle import RotatedRect

class MapElement:
    def __init__(self, image, gps_coners, px_corners=None, length_w_in_meters=0, length_h_in_meters=0):
        """
        Constructor
        :param image: Image 
        """
        self.image = image
        self.gps_corners = gps_coners
        self.px_corners = px_corners
        self.px_center = None
        self.px_width = None
        self.px_height = None
        if px_corners is not None:
            self.calculate_center_and_dims(px_corners)

    def get_image(self):
        """
        Return image
        :return: Image
        """
        return self.image

    def get_gps_corners(self):
        """
        Return position of the map element
        :return: RotatedRect
        """
        return self.gps_corners


    def set_px_corners(self, corners):
        self.px_corners = corners
        #calulate center, width and height
        self.calculate_center_and_dims(self.px_corners)

    def calculate_center_and_dims(self, px_corners):
        x_max, y_max = 0, 0
        x_min, y_min = 1000000, 1000000
        for corner in px_corners:
            x, y = corner
            if x > x_max:
                x_max = x
            if x < x_min:
                x_min = x
            if y > y_max:
                y_max = y
            if y < y_min:
                y_min = y
        self.px_width = x_max - x_min
        self.px_height = y_max - y_min
        self.px_center = (int(x_min + self.px_width/2), int(y_min + self.px_height/2))

    def set_dims(self, width, height):
        self.px_width = width
        self.px_height = height



