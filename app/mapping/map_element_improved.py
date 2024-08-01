import json
import matplotlib.pyplot as plt
import math
import numpy as np


class MapElement:
    def __init__(self, image, projected_image_dims_utm, projected_image_dims_gps, image_bounds_utm, orientations=None, projected_image_px=None, image_bounds_px=None):
        """
        Constructor
        :param image: Image
        """
        self.image = image

        # "projected_image_dims_utm" dictionary with keys "width", "height", "center", "rotation", "corners"
        # "width" and "height" width and height of projected image in m,\
        # "center" center of the image in utm,
        # "rotation" orientation of the image in degrees,
        # "corners" 4 corners of the rotated image in utm
        self.projected_image_dims_utm = projected_image_dims_utm
        self.projected_image_dims_gps = projected_image_dims_gps

        # "bounds_utm" dictionary with keys "width", "height", "center", "corners"
        # "width" and "height" outer width and height of the rotated image in m,
        # "center" center of the image in utm,
        # "corners" 4 corners of the bounds in utm
        self.image_bounds_utm = image_bounds_utm

        self.orientations = orientations

        # same as above but in pixel coordinates and relative to origin 0,0
        self.projected_image_dims_px = projected_image_px
        self.image_bounds_px = image_bounds_px


    def set_image_bounds_px(self, bounds_px):
        """
        Set bounds in pixel coordinates
        :param bounds_px: dictionary with keys "width", "height", "center", "corners"
        """
        #if there is any value of type np.float64, convert it to integer
        for key in bounds_px:
            if type(bounds_px[key]) == np.float64:
                bounds_px[key] = int(bounds_px[key])
        self.image_bounds_px = bounds_px

    def set_projected_image_dims_px(self, projected_image_dims_px):
        """
        Set corners in pixel coordinates
        :param projected_image_dims_px: dictionary with keys "width", "height", "center", "corners", "rotation"
        """
        #if there is any value of type np.float64, convert it to integer
        for key in projected_image_dims_px:
            if type(projected_image_dims_px[key]) == np.float64:
                projected_image_dims_px[key] = int(projected_image_dims_px[key])
        self.projected_image_dims_px = projected_image_dims_px

    def get_image(self):
        """
        Return image
        :return: Image
        """
        return self.image

    def get_image_bounds_utm(self):
        """
        Return bounds in utm
        :return: list of lists with [image_width_m, image_height_m, coord_x_utm, coord_y_utm, orientation]
        """
        return self.image_bounds_utm

    def get_projected_image_dims_utm(self):
        """
        Return corners in utm
        :return: list of lists with 4 lists of [x, y] coordinates
        """
        return self.projected_image_dims_utm

    def get_image_bounds_px(self):
        """
        Return bounds in pixel coordinates
        :return: list of lists with [image_width_px, image_height_px, coord_x_px, coord_y_px, orientation]
        """
        return self.image_bounds_px

    def get_projected_image_dims_px(self):
        """
        Return corners in pixel coordinates
        :return: dictionary with keys "width", "height", "center", "rotation", "corners"
        """
        return self.projected_image_dims_px

    def get_projected_image_dims_gps(self):
        """
        Return corners in gps coordinates
        :return: dictionary with keys "width", "height", "center", "corners"
        """
        return self.projected_image_dims_gps

    def get_center_coordinate(self):
        return self.rectangle.get_center()

    def set_rectangle(self, rectangle):
        self.rectangle = rectangle

    def get_orientations(self):
        return self.orientations