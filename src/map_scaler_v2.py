#!/usr/bin/env python3
__author__      = "Artur Leinweber, Max Schulte"
__copyright__ = "Copyright 2020"
__credits__ = ["None"]
__license__ = "GPL"
__maintainer__ = "Max Schulte"
__status__ = "Production"

import numpy as np
import math
from math import tan, radians, sin, cos
import webbrowser

from map_element_v2 import MapElement
from rectangle import RotatedRect
from gps import GPS

from math import pi, tan, atan2, sin, cos, sqrt
from typing import List, Tuple

import matplotlib.pyplot as plt
import numpy as np
from descartes import PolygonPatch

class MapScalerv2:

    def __init__(self, images, map_width_px, map_height_px):
        self.map_elements = list()
        self.images = images
        
        self.scaled_points = list()
        self.scale_px_per_m = 0
        self.scale_px_per_m_image = 0
        
        self.distances_m = list()
        self.distances_px = list()

        self.map_width = map_width_px
        self.map_height = map_height_px
        self.map_offset = 0

        #self.length_w_in_m, self.length_h_in_m = MapScaler.calc_length_via_fov(images)

        #self.calc_scale_px_per_m(*(self.get_min_and_max_scales()))
        self.create_map_elements()
        #self.plot_trajectory()

    def create_map_elements(self):
        for image in self.images:
            i_gps = image.exif_header.get_gps()
            i_xmp = image.exif_header.get_xmp()
            i_camera_properties = image.exif_header.get_camera_properties()
            gps_corners = self.calulate_gps_corners(i_gps.get_altitude(), i_gps.get_latitude(), i_gps.get_longitude(),
                                                    i_xmp.get_gimbal_yaw_degree(),
                                                    i_camera_properties.horizontal_fov,
                                                    i_camera_properties.vertical_fov)
            # gps_corners = self.calulate_gps_corners_a(i_gps.get_latitude(), i_gps.get_longitude(),
            #                                         i_gps.get_altitude(),  i_xmp.get_gimbal_yaw_degree(),
            #                                         i_xmp.get_gimbal_pitch_degree(),
            #                                         i_camera_properties.horizontal_fov,
            #                                         i_camera_properties.vertical_fov)
            self.map_elements.append(MapElement(image, gps_corners))


    def calculate_gps_corners_f(self, altitude, latitude, longitude, yaw, horizontal_fov, vertical_fov):
        # get camera position in world space
        camera_pos_xyz = self.calulate_xyz_from_gps(altitude, latitude, longitude)
        camera_pos_xyz = np.array(camera_pos_xyz)

        # calculate vector from camera to earth center (easy since earth center is in (0,0,0))
        camera_to_earth_center = -(camera_pos_xyz / np.linalg.norm(camera_pos_xyz))

        #rotate camera to earth center vector by yaw



    def calulate_gps_corners(self, altitude_above_ground, latitude, longitude, yaw, horizontal_fov, vertical_fov):
        # Convert angles to radians
        horizontal_fov = math.radians(horizontal_fov)
        vertical_fov = math.radians(vertical_fov)
        yaw = math.radians(yaw)

        # Calculate distance from drone to ground
        distance_to_ground = altitude_above_ground / math.cos(vertical_fov / 2)

        # Calculate width and height of image on ground
        image_width = 2 * distance_to_ground * math.tan(horizontal_fov / 2)
        image_height = 2 * distance_to_ground * math.tan(vertical_fov / 2)

        # Calculate center coordinates
        R = 6371000  # Radius of Earth in meters
        lat_center = math.radians(latitude)
        lon_center = math.radians(longitude)
        d_lat = image_height / (2 * R)
        d_lon = image_width / (2 * R * math.cos(lat_center))
        lat_center += d_lat
        lon_center += d_lon

        # Calculate coordinates of image corners
        corner_coords = []
        for dx in [-1, 1]:
            for dy in [-1, 1]:
                lat = math.asin(math.sin(lat_center) + dy * math.cos(vertical_fov / 2) / R)
                lon = lon_center + dx * math.acos(
                    (math.cos(distance_to_ground / R) - math.sin(lat_center) * math.sin(lat)) / (
                                math.cos(lat_center) * math.cos(lat)))
                lon = (lon + math.pi) % (2 * math.pi) - math.pi
                corner_coords.append((math.degrees(lat), math.degrees(lon)))

        gps_corners = []
        for corner in corner_coords:
            gps_corners.append(GPS(altitude_above_ground, corner[0], corner[1]))

        return gps_corners

    def calulate_gps_corners_e(self, drone_altitude, drone_latitude, drone_longitude, drone_heading, horizontal_fov, vertical_fov):
        # Convert latitude and longitude to radians
        drone_lat_rad = math.radians(drone_latitude)
        drone_lon_rad = math.radians(drone_longitude)

        # Convert heading to radians
        drone_heading_rad = math.radians(drone_heading)

        # Convert horizontal and vertical FOV to radians
        horizontal_fov_rad = math.radians(horizontal_fov)
        vertical_fov_rad = math.radians(vertical_fov)

        # Calculate half the width and height of the image
        image_half_width = drone_altitude * math.tan(horizontal_fov_rad / 2)
        image_half_height = drone_altitude * math.tan(vertical_fov_rad / 2)

        # Calculate the bearing from the drone's location to each corner of the image
        bearing_nw_rad = drone_heading_rad + math.atan2(-image_half_width, image_half_height)
        bearing_ne_rad = drone_heading_rad + math.atan2(image_half_width, image_half_height)
        bearing_sw_rad = drone_heading_rad + math.atan2(-image_half_width, -image_half_height)
        bearing_se_rad = drone_heading_rad + math.atan2(image_half_width, -image_half_height)

        # Calculate the distance from the drone's location to each corner of the image
        distance_nw = math.sqrt(image_half_width ** 2 + image_half_height ** 2 + drone_altitude ** 2)
        distance_ne = math.sqrt(image_half_width ** 2 + image_half_height ** 2 + drone_altitude ** 2)
        distance_sw = math.sqrt(image_half_width ** 2 + image_half_height ** 2 + drone_altitude ** 2)
        distance_se = math.sqrt(image_half_width ** 2 + image_half_height ** 2 + drone_altitude ** 2)

        # Calculate the latitude and longitude of each corner of the image
        nw_lat_rad = math.asin(math.sin(drone_lat_rad) * math.cos(distance_nw / drone_altitude) +
                               math.cos(drone_lat_rad) * math.sin(distance_nw / drone_altitude) * math.cos(bearing_nw_rad))
        nw_lon_rad = drone_lon_rad + math.atan2(
            math.sin(bearing_nw_rad) * math.sin(distance_nw / drone_altitude) * math.cos(drone_lat_rad),
            math.cos(distance_nw / drone_altitude) - math.sin(drone_lat_rad) * math.sin(nw_lat_rad))

        ne_lat_rad = math.asin(math.sin(drone_lat_rad) * math.cos(distance_ne / drone_altitude) +
                               math.cos(drone_lat_rad) * math.sin(distance_ne / drone_altitude) * math.cos(bearing_ne_rad))
        ne_lon_rad = drone_lon_rad + math.atan2(
            math.sin(bearing_ne_rad) * math.sin(distance_ne / drone_altitude) * math.cos(drone_lat_rad),
            math.cos(distance_ne / drone_altitude) - math.sin(drone_lat_rad) * math.sin(ne_lat_rad))

        sw_lat_rad = math.asin(math.sin(drone_lat_rad) * math.cos(distance_sw / drone_altitude) +
                               math.cos(drone_lat_rad) * math.sin(distance_sw / drone_altitude) * math.cos(bearing_sw_rad))
        sw_lon_rad = drone_lon_rad + math.atan2(math.sin(bearing_sw_rad) * math.sin(distance_sw / drone_altitude) * math.cos(drone_lat_rad),
                                                math.cos(distance_sw / drone_altitude) - math.sin(drone_lat_rad) * math.sin(sw_lat_rad))

        se_lat_rad = math.asin(math.sin(drone_lat_rad) * math.cos(distance_se / drone_altitude) +
                                 math.cos(drone_lat_rad) * math.sin(distance_se / drone_altitude) * math.cos(bearing_se_rad))
        se_lon_rad = drone_lon_rad + math.atan2(
            math.sin(bearing_se_rad) * math.sin(distance_se / drone_altitude) * math.cos(drone_lat_rad),
            math.cos(distance_se / drone_altitude) - math.sin(drone_lat_rad) * math.sin(se_lat_rad))

        # Convert latitude and longitude from radians to degrees
        nw_lat = math.degrees(nw_lat_rad)
        nw_lon = math.degrees(nw_lon_rad)
        ne_lat = math.degrees(ne_lat_rad)
        ne_lon = math.degrees(ne_lon_rad)
        sw_lat = math.degrees(sw_lat_rad)
        sw_lon = math.degrees(sw_lon_rad)
        se_lat = math.degrees(se_lat_rad)
        se_lon = math.degrees(se_lon_rad)

        # create a list of the corners
        corners = [(nw_lat, nw_lon), (ne_lat, ne_lon), (se_lat, se_lon), (sw_lat, sw_lon)]
        # create GPS objects for each corner
        gps_corners = []
        for corner in corners:
            gps_corners.append(GPS(drone_altitude, corner[0], corner[1]))

        return gps_corners


    def calulate_gps_corners_d(self, drone_altitude, drone_lat, drone_lon, drone_heading, hfov, vfov):
        # Convert degrees to radians
        drone_lat_rad = radians(drone_lat)
        drone_lon_rad = radians(drone_lon)
        drone_heading_rad = radians(drone_heading)
        hfov_rad = radians(hfov)
        vfov_rad = radians(vfov)

        # Calculate the distance from the drone to each corner of the image
        d_horizontal = 2 * drone_altitude * tan(hfov_rad / 2)
        d_vertical = 2 * drone_altitude * tan(vfov_rad / 2)

        # Calculate the GPS coordinates of each corner based on the drone's position and heading
        # First, calculate the north and east offsets from the drone's position
        north_offset = d_vertical * cos(drone_heading_rad) - d_horizontal * sin(drone_heading_rad)
        east_offset = d_vertical * sin(drone_heading_rad) + d_horizontal * cos(drone_heading_rad)

        # Then, calculate the GPS coordinates of each corner
        corner_1_lat = drone_lat + north_offset / 111319.9  # 1 degree of latitude is approximately 111319.9 meters
        corner_1_lon = drone_lon + east_offset / (111319.9 * cos(
            drone_lat_rad))  # 1 degree of longitude is approximately 111319.9 meters * cos(latitude)

        corner_2_lat = drone_lat + (north_offset + d_vertical) / 111319.9
        corner_2_lon = drone_lon + east_offset / (111319.9 * cos(drone_lat_rad))

        corner_3_lat = drone_lat + (north_offset + d_vertical) / 111319.9
        corner_3_lon = drone_lon + (east_offset + d_horizontal) / (111319.9 * cos(drone_lat_rad))

        corner_4_lat = drone_lat + north_offset / 111319.9
        corner_4_lon = drone_lon + (east_offset + d_horizontal) / (111319.9 * cos(drone_lat_rad))

        corners = [(corner_1_lat, corner_1_lon), (corner_2_lat, corner_2_lon), (corner_3_lat, corner_3_lon),
                (corner_4_lat, corner_4_lon)]

        coordinates_gps = []
        for coordinate in corners:
            coordinates_gps.append(GPS(drone_altitude, coordinate[0], coordinate[1]))
        return coordinates_gps


    def calulate_gps_corners_c(self, altitude, lat, lon, yaw, hfov, vfov):
        # convert degrees to radians
        lat_rad = math.radians(lat)
        lon_rad = math.radians(lon)
        yaw_rad = math.radians(yaw)
        hfov_rad = math.radians(hfov)
        vfov_rad = math.radians(vfov)
        earth_radius = 6378137  # radius of the earth in meters

        # calculate the distance from the camera to the ground
        ground_distance = altitude / math.cos(vfov_rad / 2)

        # calculate the horizontal and vertical distances from the center of the image
        horiz_distance = ground_distance * math.tan(hfov_rad / 2)
        vert_distance = ground_distance * math.tan(vfov_rad / 2)

        # calculate the four corners of the image
        # top left corner
        tl_lat = math.asin(math.sin(lat_rad) * math.cos(vert_distance / earth_radius) +
                           math.cos(lat_rad) * math.sin(vert_distance / earth_radius) * math.cos(
            yaw_rad - hfov_rad / 2))
        tl_lon = lon_rad + math.atan2(
            math.sin(yaw_rad - hfov_rad / 2) * math.sin(vert_distance / earth_radius) * math.cos(lat_rad),
            math.cos(vert_distance / earth_radius) - math.sin(lat_rad) * math.sin(tl_lat))
        # top right corner
        tr_lat = math.asin(math.sin(lat_rad) * math.cos(vert_distance / earth_radius) +
                           math.cos(lat_rad) * math.sin(vert_distance / earth_radius) * math.cos(
            yaw_rad + hfov_rad / 2))
        tr_lon = lon_rad + math.atan2(
            math.sin(yaw_rad + hfov_rad / 2) * math.sin(vert_distance / earth_radius) * math.cos(lat_rad),
            math.cos(vert_distance / earth_radius) - math.sin(lat_rad) * math.sin(tr_lat))
        # bottom left corner
        bl_lat = math.asin(math.sin(lat_rad) * math.cos(vert_distance / earth_radius) +
                           math.cos(lat_rad) * math.sin(vert_distance / earth_radius) * math.cos(
            yaw_rad - hfov_rad / 2))
        bl_lon = lon_rad + math.atan2(
            math.sin(yaw_rad - hfov_rad / 2) * math.sin(vert_distance / earth_radius) * math.cos(lat_rad),
            math.cos(vert_distance / earth_radius) - math.sin(lat_rad) * math.sin(bl_lat))
        # bottom right corner
        br_lat = math.asin(math.sin(lat_rad) * math.cos(vert_distance / earth_radius) +
                           math.cos(lat_rad) * math.sin(vert_distance / earth_radius) * math.cos(
            yaw_rad + hfov_rad / 2))
        br_lon = lon_rad + math.atan2(
            math.sin(yaw_rad + hfov_rad / 2) * math.sin(vert_distance / earth_radius) * math.cos(lat_rad),
            math.cos(vert_distance / earth_radius) - math.sin(lat_rad) * math.sin(br_lat))

        # convert back to degrees
        tl_lat = math.degrees(tl_lat)
        tl_lon = math.degrees(tl_lon)
        tr_lat = math.degrees(tr_lat)
        tr_lon = math.degrees(tr_lon)
        bl_lat = math.degrees(bl_lat)
        bl_lon = math.degrees(bl_lon)
        br_lat = math.degrees(br_lat)
        br_lon = math.degrees(br_lon)

        coodinates = [[tl_lat, tl_lon], [tr_lat, tr_lon], [bl_lat, bl_lon] , [br_lat, br_lon]]
        coordinates_gps = []
        for coordinate in coodinates:
            coordinates_gps.append(GPS(altitude, coordinate[0], coordinate[1]))
        return coordinates_gps


    def calulate_gps_corners(self, altitude, latitude, longitude, yaw, hfov, vfov):
        print("calulate_gps_corners with altitude: " + str(altitude) + " latitude: " + str(latitude) + " longitude: " + str(longitude) + " yaw: " + str(yaw) + " hfov: " + str(hfov) + " vfov: " + str(vfov))
        # Convert drone's yaw angle from degrees to radians
        yaw_rad = math.radians(yaw)

        # Calculate half of the horizontal and vertical field of view angles
        hfov_half = math.radians(hfov / 2)
        vfov_half = math.radians(vfov / 2)

        # Calculate the distance from the drone to the image plane (assuming flat ground)
        distance = altitude / math.cos(vfov_half)

        # Calculate the four corners of the image in image plane coordinates
        top_left = [-distance * math.tan(hfov_half), distance * math.tan(vfov_half)]
        top_right = [distance * math.tan(hfov_half), distance * math.tan(vfov_half)]
        bottom_right = [distance * math.tan(hfov_half), -distance * math.tan(vfov_half)]
        bottom_left = [-distance * math.tan(hfov_half), -distance * math.tan(vfov_half)]

        # Rotate the image plane coordinates based on the drone's yaw angle
        top_left_rot = [
            top_left[0] * math.cos(yaw_rad) - top_left[1] * math.sin(yaw_rad),
            top_left[0] * math.sin(yaw_rad) + top_left[1] * math.cos(yaw_rad)
        ]
        top_right_rot = [
            top_right[0] * math.cos(yaw_rad) - top_right[1] * math.sin(yaw_rad),
            top_right[0] * math.sin(yaw_rad) + top_right[1] * math.cos(yaw_rad)
        ]
        bottom_right_rot = [
            bottom_right[0] * math.cos(yaw_rad) - bottom_right[1] * math.sin(yaw_rad),
            bottom_right[0] * math.sin(yaw_rad) + bottom_right[1] * math.cos(yaw_rad)
        ]
        bottom_left_rot = [
            bottom_left[0] * math.cos(yaw_rad) - bottom_left[1] * math.sin(yaw_rad),
            bottom_left[0] * math.sin(yaw_rad) + bottom_left[1] * math.cos(yaw_rad)
        ]

        # Convert image plane coordinates to GPS coordinates
        earth_radius = 6371000  # Earth's radius in meters
        lat_conv = 180 / math.pi / earth_radius
        lon_conv = lat_conv / math.cos(math.radians(latitude))

        top_left_gps = GPS(
            altitude,
            latitude + top_left_rot[1] * lat_conv,
            longitude + top_left_rot[0] * lon_conv
        )
        top_right_gps = GPS(
            altitude,
            latitude + top_right_rot[1] * lat_conv,
            longitude + top_right_rot[0] * lon_conv
        )
        bottom_right_gps = GPS(
            altitude,
            latitude + bottom_right_rot[1] * lat_conv,
            longitude + bottom_right_rot[0] * lon_conv
        )
        bottom_left_gps = GPS(
            altitude,
            latitude + bottom_left_rot[1] * lat_conv,
            longitude + bottom_left_rot[0] * lon_conv
        )

        print("results: " + str(top_left_gps) + " " + str(top_right_gps) + " " + str(bottom_right_gps) + " " + str(bottom_left_gps))

        # Return the four GPS coordinates of the projected image corners
        return top_left_gps, top_right_gps, bottom_right_gps, bottom_left_gps

    def calulate_gps_corners_a(self,
        drone_latitude: float,
        drone_longitude: float,
        drone_altitude: float,
        camera_yaw: float,
        camera_pitch: float,
        horizontal_fov: float,
        vertical_fov: float,
    ) -> List[GPS]:

        # Constants for Earth's radius and conversion factors
        EARTH_RADIUS = 6378137.0
        DEG_TO_RAD = pi / 180.0
        RAD_TO_DEG = 180.0 / pi

        # Convert camera yaw and pitch angles to radians
        yaw_rad = camera_yaw * DEG_TO_RAD
        pitch_rad = camera_pitch * DEG_TO_RAD

        # Compute the distances to the image corners
        half_horizontal_fov = horizontal_fov / 2.0
        half_vertical_fov = vertical_fov / 2.0
        x_max = drone_altitude * tan(half_horizontal_fov * DEG_TO_RAD)
        y_max = drone_altitude * tan(half_vertical_fov * DEG_TO_RAD)

        # Compute the image corner coordinates in camera frame
        corners = [
            (-x_max, -y_max),
            (x_max, -y_max),
            (x_max, y_max),
            (-x_max, y_max)
        ]

        # Rotate the corners based on camera yaw angle
        rot_corners = []
        for corner in corners:
            x = corner[0] * cos(yaw_rad) - corner[1] * sin(yaw_rad)
            y = corner[0] * sin(yaw_rad) + corner[1] * cos(yaw_rad)
            rot_corners.append((x, y))

        # Compute the pitch angle rotation matrix
        pitch_rot = [
            [1, 0, 0],
            [0, cos(pitch_rad), -sin(pitch_rad)],
            [0, sin(pitch_rad), cos(pitch_rad)]
        ]

        # Rotate the corners based on camera pitch angle
        proj_corners = []
        for corner in rot_corners:
            p = [corner[0], corner[1], drone_altitude]
            x, y, z = [sum([pitch_rot[i][j] * p[j] for j in range(3)]) for i in range(3)]

            # Compute the projected longitude and latitude
            lon = drone_longitude + atan2(x, EARTH_RADIUS * cos(drone_latitude * DEG_TO_RAD))
            lat = atan2(y, sqrt(x**2 + (EARTH_RADIUS * cos(drone_latitude * DEG_TO_RAD))**2))
            lat = lat * RAD_TO_DEG
            lon = lon * RAD_TO_DEG

            # Create a GPS object with altitude, latitude, and longitude
            proj_corners.append(GPS(0, lat, lon))

        # Return the projected image corner GPS objects
        return proj_corners

    def get_map_elements(self):
        return self.map_elements