#!/usr/bin/env python3
__author__      = "Artur Leinweber"
__copyright__ = "Copyright 2020"
__credits__ = ["None"]
__license__ = "GPL"
__version__ = "1.0.1"
__maintainer__ = "Artur Leinweber"
__email__ = "arturleinweber@live.de"
__status__ = "Production"

import math
import numpy as np


class CameraProperties:
    def __init__(self, model, fov, fl):
        """
        Constructor
        """
        self.model = model
        self.fov = fov
        self.fl = fl
        self.vertical_fov = None
        self.sensor_width = None
        self.sensor_height = None

    def __str__(self):
        """
        Represent the string interpretation of XMP values.
        :return: string representation
        """
        return "Model: " + str(self.model) + "\n" \
               + "FOV: " + str(self.fov) + "\n" \
               + "Focal Length: " + str(self.fl) + "\n"

    def get_model(self):
        """
        Returning model name of the camera.
        :return: string representstion of the model name
        """
        return self.model

    def get_fov(self):
        """
        Returning field of view of the camera.
        :return: float value
        """
        return self.fov

    def get_focal_length(self):
        """
        Returning focal length of the camera.
        :return: float value
        """
        return self.fl

    def get_sensor_size(self):
        return (self.sensor_width, self.sensor_height)

    def get_vertical_fov(self):
        return self.vertical_fov

    def set_sensor_size(self, width, height):
        self.sensor_width = width
        self.sensor_height = height
    
    def set_vertical_fov(self, v_fov):
        self.vertical_fov = v_fov
