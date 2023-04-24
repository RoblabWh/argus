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
from math import pi, tan, atan, atan2, sin, cos, sqrt


class CameraProperties:
    def __init__(self, model, fov, fl, fl35mm=0, acpect_ratio=1.0):
        """
        Constructor
        """
        self.model = model
        self.fov = fov
        self.fl = fl
        self.fl35mm = fl35mm
        self.vertical_fov = None
        self.horizontal_fov = None
        self.sensor_width = None
        self.sensor_height = None
        if self.fl35mm != 0:
            self.calculate_fovs(self.fl35mm, acpect_ratio)

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
        pass
        #self.vertical_fov = v_fov

    def calculate_fovs(self, focal_length_35mm, aspect_ratio):
        """
        Calculates the horizontal and vertical field of view based on the focal length in the 35mm format and the aspect ratio.
        :param focal_length_35mm: Focal length in the 35mm format
        :param aspect_ratio: Image aspect ratio (width / height)
        :return: Tuple containing the horizontal and vertical field of view in degrees
        """

        w = 36.0 #width of full frame sensor in mm
        # height based on width and aspect ratio
        h = w / aspect_ratio

        horizontal_fov = 2 * atan2(w / 2, focal_length_35mm)
        vertical_fov = 2 * atan2(h / 2, focal_length_35mm)
        diagonal_fov = 2 * atan2(sqrt(w**2 + h**2) / 2, focal_length_35mm)


        # Convert to degrees and return as tuple
        self.vertical_fov = vertical_fov * 180.0 / pi
        self.horizontal_fov = horizontal_fov * 180.0 / pi
        self.fov = diagonal_fov * 180.0 / pi

        print("calculated fovs based on 35mm focal length: ", focal_length_35mm, "and aspect ratio: ", aspect_ratio, "horizontal fov: ", self.horizontal_fov, "vertical fov: ", self.vertical_fov, "diagonal fov: ", self.fov)