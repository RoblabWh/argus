#!/usr/bin/env python3
__author__      = "Artur Leinweber, Max Schulte"
__copyright__ = "Copyright 2020"
__credits__ = ["None"]
__license__ = "GPL"
__maintainer__ = "Max Schulte"
__status__ = "Production"

import numpy as np
import math
#import webbrowser

from .map_element import MapElement
from .rectangle import RotatedRect
from .gps import GPS

import matplotlib.pyplot as plt
import numpy as np
from descartes import PolygonPatch

class MapScaler:

    def __init__(self, images, map_width_px, map_height_px):
        self.map_elements = list()
        self.images = images
        
        self.scaled_points = list()
        self.scale_px_per_m = 0
        self.scale_px_per_m_image = 0
        
        self.distances_m = list()
        self.distances_px = list()

        self.map_width_px = map_width_px
        self.map_height_px = map_height_px
        self.map_offset = 0

        self.length_w_in_m, self.length_h_in_m = MapScaler.calc_length_via_fov(images)

        self.calc_scale_px_per_m(*(self.get_min_and_max_scales()))
        self.create_map_elements()



    def get_min_and_max_scales(self):
        #Searching for Min and Max of X and Y for creating our Map
        min_x = float("inf")
        min_y = float("inf")
        max_x = float("-inf")
        max_y = float("-inf")

        for image in self.images:
            x, y = image.get_exif_header().get_gps().get_cartesian()
            if (min_x > x):
                min_x = x

            if (min_y > y):
                min_y = y

            if (max_x < x):
                max_x = x

            if (max_y < y):
                max_y = y
        return min_x, max_x, min_y, max_y

    def calc_scale_px_per_m(self, min_x, max_x, min_y, max_y):
        distances_m = list()
        distances_px = list()

        x_coord = list()
        y_coord = list()

        longest_side = float(max(max_x-min_x, max_y-min_y))

        for image in self.images:
            x, y = image.get_exif_header().get_gps().get_cartesian()
            x = (float(x - min_x) / longest_side) * self.map_width_px
            y = (float(y - min_y) / longest_side) * self.map_width_px
            
            x_coord.append(x)
            y_coord.append(y)
            self.scaled_points.append((x, y))

        for i in range(len(self.scaled_points)-1):
            x1,y1 = self.scaled_points[i]
            x2,y2 = self.scaled_points[i+1]
            distances_px.append(math.sqrt(((x1-x2)*(x1-x2))+((y1-y2)*(y1-y2))))        

        for i in range(len(self.images)-1):
            gps1 = self.images[i].get_exif_header().get_gps()
            gps2 = self.images[i+1].get_exif_header().get_gps()
            distances_m.append(GPS.calc_distance_between(gps1, gps2))
        
        scale_px_per_m_lst = list()
        for i in range(len(self.images)-1):
            if distances_m[i] > 0:
                scale_px_per_m_lst.append(distances_px[i] / distances_m[i])
            
        self.scale_px_per_m = np.mean(np.asarray(scale_px_per_m_lst))

    def create_map_elements(self):
        image_width_px = list()
        image_height_px = list()
        for i in range(len(self.images)):
            image_width_px.append(int(self.length_w_in_m[i] * self.scale_px_per_m))
            image_height_px.append(int(self.length_h_in_m[i] * self.scale_px_per_m))

        self.map_offset = int(math.sqrt(((max(image_width_px))*(max(image_width_px)))+((max(image_height_px))*(max(image_height_px)))) * 2)

        ref = self.images[1].get_exif_header().get_xmp().get_flight_yaw_degree() - self.images[1].get_exif_header().get_xmp().get_gimbal_yaw_degree()
        for i, image in enumerate(self.images):
            cx, cy = self.scaled_points[i]
            gimbal_yaw_degree = -(image.get_exif_header().get_xmp().get_gimbal_yaw_degree() + ref)
            rect = RotatedRect(int(self.map_offset/2) + cx, int(self.map_offset/2) + cy , image_width_px[i], image_height_px[i], gimbal_yaw_degree)
            self.map_elements.append(MapElement(image, rect))



    def get_map_offset(self):
        return self.map_offset

    def get_map_elements(self):
        return self.map_elements

    def get_area_in_m(self):
        max_x = float("-inf")
        max_y = float("-inf")
        for point in self.scaled_points:
            x, y = point
            if (max_x < x):
                max_x = x

            if (max_y < y):
                max_y = y
        return max_x/self.scale_px_per_m * max_y/self.scale_px_per_m 

    def get_avg_altitude(self):
        avg_altitude = 0
        for map_element in self.map_elements:
            avg_altitude = avg_altitude + map_element.get_image().get_exif_header().get_gps().get_altitude()
        avg_altitude = str(avg_altitude/len(self.map_elements))
        return avg_altitude

    @staticmethod
    def calc_length_via_fov(images):
        length_w_in_m = list()
        length_h_in_m = list()
        vertical_fov = 0
        horizontal_fov = 0
        sensor_width_mm = 0
        sensor_height_mm = 0

        for image in images:
            image_header = image.get_exif_header()
            relative_altitude = image_header.get_gps().get_altitude()
            camera_properties = image_header.get_camera_properties()
            focal_length = camera_properties.get_focal_length()
            horizontal_fov = camera_properties.get_fov()
            image_width = image.get_width()
            image_height = image.get_height()
            print("focal length: " + str(focal_length), "horizontal fov: " + str(horizontal_fov))

            sensor_width_mm = math.tan(math.radians(horizontal_fov)/2) * (2*focal_length)
            #print(sensor_width_mm) 
            sensor_height_mm = sensor_width_mm/(image_width/image_height)
            #print(sensor_height_mm)
            vertical_fov = math.degrees(2*math.atan2(sensor_height_mm/2,focal_length))            
            
            camera_properties.set_sensor_size(sensor_width_mm, sensor_height_mm)
            camera_properties.set_vertical_fov(vertical_fov)
            #print("relative_altitude:", relative_altitude)
            roh_horizontal = 180.0 - 90.0 - (horizontal_fov / 2.0)
            roh_vertical = 180.0 - 90.0 - (vertical_fov / 2.0)
            horizontal_length_m = (relative_altitude * 2.0) / (np.tan(np.deg2rad(roh_horizontal)))
            vertical_length_m = (relative_altitude * 2.0) / (np.tan(np.deg2rad(roh_vertical)))
            length_w_in_m.append(horizontal_length_m)
            length_h_in_m.append(vertical_length_m)
        return (length_w_in_m, length_h_in_m)

    def get_middle_gps(self):
        return (self.map_elements[int(len(self.map_elements)/2)].get_image().get_exif_header().get_gps())

    def get_scale_px_per_m(self):
        return self.scale_px_per_m

    def get_scale_m_per_px(self):
        return 1.0/self.scale_px_per_m

    def calculate_distance_between_corner_and_origin_in_px(self, corner_location, origin_location):
        x_corner, y_corner = corner_location
        x_origin, y_origin = origin_location

        distance = math.sqrt(math.pow(x_corner - x_origin, 2) + math.pow(y_corner - y_origin, 2))
        #print("Distance to Corner:" + str(distance) + "[px]")
        return distance

    def calculate_distance_between_object_and_uav_in_m(self, corner_location, origin_location):
        x_origin, y_origin = origin_location
        x_corner, y_corner = corner_location

        x_corner = x_corner * self.get_scale_m_per_px()
        y_corner = y_corner * self.get_scale_m_per_px()

        x_origin = x_origin * self.get_scale_m_per_px()
        y_origin = y_origin * self.get_scale_m_per_px()

        distance_m = math.sqrt(math.pow(x_corner-x_origin, 2) + math.pow(y_corner-y_origin, 2))
        #print("Distance to Corner:" + str(distance_m) + "[m]")
        return distance_m

    def calculate_angle_distance_between_corner_and_origin(self, distance, corner_location, origin_location):

        x_origin, y_origin = origin_location
        x_corner, y_corner = corner_location
        #print("x_origin, y_origin: ", x_origin, y_origin)
        #calculate_angle_distance_between_object_and_uav
        if((y_origin - y_corner) >= 0):
            if (x_corner - x_origin == 0):
                return 0
                             
            rad = (math.acos((x_corner - x_origin) / distance))
        else:
            rad = 2 * math.pi - (math.acos((x_corner - x_origin) / distance))

        grad = math.degrees(rad)
        #print "Grad: " + str(grad)
        if ((grad - 90) < 0 ):
            grad = 360 - (90 - grad)

        else:
            grad = grad - 90
        
        return grad



    def calculate_corner_gps_coordinates(self, origin_gps, origin_location, corner_location):
        CONST_RADIUS_EARTH_METER = 6378137.000
        distance_px = self.calculate_distance_between_corner_and_origin_in_px(corner_location, origin_location)
        distance = self.calculate_distance_between_object_and_uav_in_m(corner_location, origin_location)
        angle = self.calculate_angle_distance_between_corner_and_origin(distance_px, corner_location, origin_location)
        # Vielleicht muss eine Fallunterscheidung hin wegen -180 und +180
        #new_angle = (self.uav_flight_yaw_degree + 540) % 360 - angle
        #new_angle = (-angle + 540) % 360 - 180
        new_angle = angle + 180
     
        #print(new_angle)

        origin_gps_latitude = origin_gps.get_latitude()# - 0.00005
        origin_gps_longitude = origin_gps.get_longitude()# - 0.0001

        new_latitude = math.asin(math.sin(math.radians(origin_gps_latitude)) *
                                 math.cos(distance / CONST_RADIUS_EARTH_METER) +
                                 math.cos(math.radians(origin_gps_latitude)) *
                                 math.sin(distance / CONST_RADIUS_EARTH_METER) *
                                 math.cos(math.radians(new_angle)))

        new_longitude = math.radians(origin_gps_longitude) + \
                        math.atan2(math.sin(math.radians(new_angle)) *
                                   math.sin(distance / CONST_RADIUS_EARTH_METER) *
                                   math.cos(math.radians(origin_gps_latitude)),
                                   math.cos(distance / CONST_RADIUS_EARTH_METER) -
                                   math.sin(math.radians(origin_gps_latitude))*math.sin(new_latitude))
        lat = math.degrees(new_latitude)
        lng = math.degrees(new_longitude)
        #webbrowser.open("https://www.google.com/maps/search/?api=1&query="+str(lat)+","+str(lng)) 
        return GPS(self.get_avg_altitude(),lat,lng)



