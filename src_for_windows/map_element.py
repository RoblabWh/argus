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
    def __init__(self, image, rotated_rectangle):
        """
        Constructor
        :param image: Image 
        """
        self.image = image
        self.rectangle = rotated_rectangle

    def get_image(self):
        """
        Return image
        :return: Image
        """
        return self.image

    def get_rotated_rectangle(self):
        """
        Return position of the map element
        :return: RotatedRect
        """
        return self.rectangle

    def get_center_coordinate(self):
        return self.rectangle.get_center()

    def set_rectangle(self, rectangle):
        self.rectangle = rectangle
        

