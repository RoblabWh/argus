import pyproj
import numpy as np
import math

from .map_element_improved import MapElement
from .rectangle import RotatedRect
from .gps import GPS


class MapScalerImproved:

    def __init__(self, images, map_width_px, map_height_px):
        self.map_size_px = map_width_px
        self.meter_to_px_ratio = -1
        self.map_bounds_utm = []  # dictionary with keys "width", "height", "center", "corners"
        self.map_bounds_gps = []  # dictionary with keys "width", "height", "center", "corners"
        self.map_dimensions_px = []  # width, height
        self.map_elements = []

        self.zone = self.calculate_zone(images[0].exif_header.get_gps().get_longitude())

        self.map_elements = self.create_map_elements(images, self.zone)
        self.map_bounds_gps = self.convert_utm_bounds_to_gps(self.map_bounds_utm, self.zone)
        self.map_dimensions_px = self.calculate_map_dimensions(self.map_bounds_utm, self.meter_to_px_ratio)

        all_corners_gps = [map_element.get_projected_image_dims_gps()["corners"] for map_element in self.map_elements]
        min_x, min_y, max_x, max_y = self.calculate_min_max(all_corners_gps)
        #self.map_bounds_gps["corners"] = [[min_x, min_y], [max_x, min_y], [max_x, max_y], [min_x, max_y]]



    def create_map_elements(self, images, zone):
        """
        Create map elements from images
        Calculate everything needed for the improved map elements -> bounds_px, bounds_utm, corners_utm
        :param images:
        :return: list of map_elements
        """
        map_elements = []

        utm_coords = []
        gps_coords = []
        for i in range(len(images)):
            image = images[i]
            gps_lat = image.exif_header.get_gps().get_latitude()
            gps_long = image.exif_header.get_gps().get_longitude()
            utm = self.convert_gps_to_utm(gps_long, gps_lat, zone)
            utm_coords.append(utm)
            gps_coords.append([gps_long, gps_lat])

        reference_yaw = self.calculate_reference_yaw(images, utm_coords)

        # reference_yaw = images[0].get_exif_header().get_xmp().get_flight_yaw_degree() \
        #                 - images[0].get_exif_header().get_xmp().get_gimbal_yaw_degree()
        #print("reference_yaw: ", reference_yaw, flush=True)
        #reference_yaw = 0
        for i in range(len(images)):
            image = images[i]
            # reference_yaw = image.get_exif_header().get_xmp().get_flight_yaw_degree() \
            #                 - image.get_exif_header().get_xmp().get_gimbal_yaw_degree()
            projected_image_dims_utm, bounds_utm, orientations = self.calculate_image_dims_utm(image, utm_coords[i], gps_coords[i], reference_yaw, zone)
            projected_image_dims_gps = self.convert_utm_bounds_to_gps(projected_image_dims_utm, zone)
            map_elements.append(MapElement(image, projected_image_dims_utm, projected_image_dims_gps, bounds_utm, orientations))

        all_corners_utm = [map_element.get_projected_image_dims_utm()["corners"] for map_element in map_elements]

        min_x, min_y, max_x, max_y = self.calculate_min_max(all_corners_utm)
        outer_width = max_x - min_x
        outer_height = max_y - min_y

        meter_to_px_ratio = self.map_size_px / max(outer_width, outer_height)

        for i in range(len(map_elements)):
            projected_image_dims_px = self.convert_to_px(map_elements[i].projected_image_dims_utm, meter_to_px_ratio, min_x, min_y)
            image_bounds_px = self.convert_to_px(map_elements[i].image_bounds_utm, meter_to_px_ratio, min_x, min_y)
            map_elements[i].set_image_bounds_px(image_bounds_px)
            map_elements[i].set_projected_image_dims_px(projected_image_dims_px)
            #print("map_element ", i, " bounds_px: ", image_bounds_px, flush=True)
            #print("map_element ", i, " projected_image_dims_px: ", projected_image_dims_px, flush=True)

        self.meter_to_px_ratio = meter_to_px_ratio
        print("|| meter_to_px_ratio: ", meter_to_px_ratio, flush=True)
        self.map_bounds_utm = {"width": outer_width,
                               "height": outer_height,
                               "center": [min_x + outer_width / 2, min_y + outer_height / 2],
                               "corners": [[min_x, min_y], [max_x, min_y], [max_x, max_y], [min_x, max_y]]}


        return map_elements

    def get_map_elements(self):
        return self.map_elements

    def calculate_image_dims_utm(self, image, utm, gps, rotation_offset, zone):
        altitude = image.get_exif_header().get_gps().get_altitude()
        coord_x_utm = utm[0]
        coord_y_utm = utm[1]

        #grid divergence
        utm_grid_north_divergence = self.calculate_grid_north_convergence(zone, *gps)

        # camera and photo specs
        focal_length = image.get_exif_header().camera_properties.get_focal_length()
        fov_horizontal = image.get_exif_header().camera_properties.get_fov()
        image_width_px = image.get_width()
        image_height_px = image.get_height()
        orientation = image.get_exif_header().get_xmp().get_gimbal_yaw_degree() + rotation_offset + utm_grid_north_divergence # degrees
        orientations = {"gimbal": image.get_exif_header().get_xmp().get_gimbal_yaw_degree(),
                        "flight": image.get_exif_header().get_xmp().get_flight_yaw_degree(),
                        "corrected": orientation}
        print("orientations: ", orientations, flush=True)
        print("offset: ", rotation_offset, flush=True)

        sensor_width_mm = math.tan(math.radians(fov_horizontal) / 2) * (2 * focal_length)
        sensor_height_mm = sensor_width_mm / (image_width_px / image_height_px)
        vertical_fov = math.degrees(2 * math.atan2(sensor_height_mm / 2, focal_length))

        roh_horizontal = 180.0 - 90.0 - (fov_horizontal / 2.0)
        roh_vertical = 180.0 - 90.0 - (vertical_fov / 2.0)
        image_width_m = (altitude * 2.0) / (np.tan(np.deg2rad(roh_horizontal)))
        image_height_m = (altitude * 2.0) / (np.tan(np.deg2rad(roh_vertical)))

        # corners
        bounds_top_left = [coord_x_utm - image_width_m / 2, coord_y_utm + image_height_m / 2]
        bounds_top_right = [coord_x_utm + image_width_m / 2, coord_y_utm + image_height_m / 2]
        bounds_bottom_left = [coord_x_utm - image_width_m / 2, coord_y_utm - image_height_m / 2]
        bounds_bottom_right = [coord_x_utm + image_width_m / 2, coord_y_utm - image_height_m / 2]

        # rotate the four corner points around the relative center (coord_x_utm, coord_y_utm) by the orientation
        c_top_left_utm = self.rotate_point(bounds_top_left, coord_x_utm, coord_y_utm, -orientation)
        c_top_right_utm = self.rotate_point(bounds_top_right, coord_x_utm, coord_y_utm, -orientation)
        c_bottom_right_utm = self.rotate_point(bounds_bottom_right, coord_x_utm, coord_y_utm, -orientation)
        c_bottom_left_utm = self.rotate_point(bounds_bottom_left, coord_x_utm, coord_y_utm, -orientation)

        corners_utm = [c_top_left_utm, c_top_right_utm, c_bottom_right_utm, c_bottom_left_utm]
        projected_image_dims_utm = {"width": image_width_m,
                                    "height": image_height_m,
                                    "center": [coord_x_utm, coord_y_utm],
                                    "rotation": orientation,
                                    "corners": corners_utm}
        bounds_utm = self.calculate_bounds_utm(projected_image_dims_utm)

        return projected_image_dims_utm, bounds_utm, orientations

    def calculate_bounds_utm(self, projected_image_dims_utm):
        corners = projected_image_dims_utm["corners"]
        min_x, min_y, max_x, max_y = self.calculate_min_max([corners])
        bounds = {}  # width, height, center, corners
        bounds["width"] = max_x - min_x
        bounds["height"] = max_y - min_y
        bounds["center"] = projected_image_dims_utm["center"]
        bounds["corners"] = [[min_x, min_y], [max_x, min_y], [max_x, max_y], [min_x, max_y]]
        return bounds

    def convert_gps_to_utm(self, long, lat, zone):
        """
        Convert GPS coordinates (longitude, latitude) to UTM coordinates in the specified zone.

        Parameters:
        long (float): Longitude in degrees.
        lat (float): Latitude in degrees.
        zone (int): UTM zone number.

        Returns:
        tuple: UTM coordinates (easting, northing).
        """
        # Define the WGS84 and UTM projections using EPSG codes
        wgs84_crs = "EPSG:4326"
        utm_crs = f"EPSG:326{zone:02d}" if lat >= 0 else f"EPSG:327{zone:02d}"

        # Create a transformer object
        transformer = pyproj.Transformer.from_crs(wgs84_crs, utm_crs)

        # Transform the coordinates
        easting, northing = transformer.transform(lat, long)

        return (easting, northing)

    def calculate_zone(self, long):
        return int((long + 180) / 6) + 1

    def rotate_point(self, point, center_x, center_y, angle):
        angle = math.radians(angle)
        x = point[0] - center_x
        y = point[1] - center_y
        new_x = x * math.cos(angle) - y * math.sin(angle)
        new_y = x * math.sin(angle) + y * math.cos(angle)
        return [new_x + center_x, new_y + center_y]

    def calculate_min_max(self, all_corners_utm):
        min_x = float("inf")
        min_y = float("inf")
        max_x = float("-inf")
        max_y = float("-inf")
        for i in range(len(all_corners_utm)):
            for j in range(len(all_corners_utm[i])):
                if all_corners_utm[i][j][0] < min_x:
                    min_x = all_corners_utm[i][j][0]
                if all_corners_utm[i][j][0] > max_x:
                    max_x = all_corners_utm[i][j][0]
                if all_corners_utm[i][j][1] < min_y:
                    min_y = all_corners_utm[i][j][1]
                if all_corners_utm[i][j][1] > max_y:
                    max_y = all_corners_utm[i][j][1]
        return min_x, min_y, max_x, max_y

    def convert_to_px(self, dict_utm, factor, min_x=0, min_y=0):
        dict_px = {}
        for key in dict_utm:
            if key == "center":
                dict_px[key] = [(dict_utm[key][0] - min_x) * factor, (dict_utm[key][1] - min_y) * factor]
            elif key == "corners":
                corners_px = []
                for corner in dict_utm[key]:
                    corners_px.append([(corner[0] - min_x) * factor, (corner[1] - min_y) * factor])
                dict_px[key] = corners_px
            elif key == "width" or key == "height":
                dict_px[key] = dict_utm[key] * factor
            else:
                dict_px[key] = dict_utm[key]
        return dict_px

    def convert_utm_bounds_to_gps(self, map_bounds_utm, zone):
        map_bounds_gps = {}
        map_bounds_gps["width"] = map_bounds_utm["width"]
        map_bounds_gps["height"] = map_bounds_utm["height"]
        map_bounds_gps["center"] = self.convert_utm_to_gps(map_bounds_utm["center"][0], map_bounds_utm["center"][1], zone)
        corners_gps = []
        for corner in map_bounds_utm["corners"]:
            corners_gps.append(self.convert_utm_to_gps(corner[0], corner[1], zone))
        map_bounds_gps["corners"] = corners_gps
        return map_bounds_gps

    def convert_utm_to_gps(self, utm_x, utm_y, zone):
        """
        Convert UTM coordinates to GPS coordinates (longitude, latitude) in the specified zone.

        Parameters:
        utm_x (float): UTM easting.
        utm_y (float): UTM northing.
        zone (int): UTM zone number.

        Returns:
        tuple: GPS coordinates (longitude, latitude).
        """
        # Define the WGS84 and UTM projections using EPSG codes
        wgs84_crs = "EPSG:4326"
        utm_crs = f"EPSG:326{zone:02d}" if utm_y >= 0 else f"EPSG:327{zone:02d}"

        # Create a transformer object
        transformer = pyproj.Transformer.from_crs(utm_crs, wgs84_crs)

        # Transform the coordinates
        long, lat = transformer.transform(utm_x, utm_y)

        return long, lat

    def calculate_map_dimensions(self, map_bounds_utm, meter_to_px_ratio):
        width_px = int(map_bounds_utm["width"] * meter_to_px_ratio)
        height_px = int(map_bounds_utm["height"] * meter_to_px_ratio)
        return [width_px, height_px]


    def generate_debug_coords_grid(self):
        #get bounds and determine longest side
        width, height = self.map_bounds_utm["width"], self.map_bounds_utm["height"]
        corners = self.map_bounds_utm["corners"]

        #determine how many lines we need
        meters_per_line = 20

        horizontal_lines = []
        for i in range(0, int(width/meters_per_line)+2):
            line = []
            for j in range(0, int(height/meters_per_line)+2):
                x, y = corners[0][0] + i * meters_per_line, corners[0][1] + j * meters_per_line
                if x > corners[2][0]:
                    x = corners[2][0]
                if y > corners[2][1]:
                    y = corners[2][1]
                x, y = self.convert_utm_to_gps(x, y, self.zone)
                line.append([x, y])
            horizontal_lines.append(line)

        vertical_lines = []
        #restructure the horizontal lines to vertical lines by iterating over the first element of each line
        for i in range(len(horizontal_lines[0])):
            line = []
            for j in range(len(horizontal_lines)):
                line.append(horizontal_lines[j][i])
            vertical_lines.append(line)

        grid = vertical_lines + horizontal_lines

        return grid

    def calculate_reference_yaw(self, images, utm_coords):
        #calculate the reference yaw
        # go through all images and find three images in a row with the orientation (gimbal_yaw_degree) within a margin of 5 degrees
        # calculate the average orientation of these three images
        # set the reference yaw to the average orientation
        margin_orientation_degrees = 1.5
        margin_trajectory_degrees = 5

        images_len = len(images)
        if images_len < 3:
            dumb_offset = self.calc_dumb_offset(images[0])
            return dumb_offset


        for i in range(len(images)-2):
            roi = images[i:i+3]

            orientation_diff_degrees = roi[0].get_exif_header().get_xmp().get_gimbal_yaw_degree() - roi[1].get_exif_header().get_xmp().get_gimbal_yaw_degree()
            if orientation_diff_degrees > margin_orientation_degrees:
                continue

            orientation_diff_degrees = roi[1].get_exif_header().get_xmp().get_gimbal_yaw_degree() - roi[2].get_exif_header().get_xmp().get_gimbal_yaw_degree()
            if orientation_diff_degrees > margin_orientation_degrees:
                continue

            v_diff_a = np.array(utm_coords[i+1]) - np.array(utm_coords[i])
            v_diff_b = np.array(utm_coords[i+2]) - np.array(utm_coords[i+1])
            angle = np.arccos(np.dot(v_diff_a, v_diff_b) / (np.linalg.norm(v_diff_a) * np.linalg.norm(v_diff_b)))
            angle = np.degrees(angle)
            if angle < margin_trajectory_degrees:
                print("using images: ", i, i+1, i+2, flush=True)
                print("ANGLE", angle)
                print("based on vectors:  va", v_diff_a, "vb", v_diff_b, flush=True)
                reference_yaw = np.arctan2(v_diff_b[0], v_diff_b[1])
                reference_yaw = np.degrees(reference_yaw)
                print("REFERENCE ANGLE", reference_yaw, flush=True)
                print("based on vectors: ", v_diff_b, flush=True)
                reference_yaw = reference_yaw - roi[1].get_exif_header().get_xmp().get_gimbal_yaw_degree()
                print(roi, flush=True)
                print("REFERENCE YAW", reference_yaw, flush=True)
                return float(reference_yaw)
        return self.calc_dumb_offset(images[0])


    def calc_dumb_offset(self, image):
        print("DUMB OFFSET", flush=True)
        return image.get_exif_header().get_xmp().get_flight_yaw_degree() - image.get_exif_header().get_xmp().get_gimbal_yaw_degree()



    def calculate_grid_north_convergence(self, zone, long, lat):
        #γ = arctan [tan (λ - λ0) × sin φ]
        #
        # where
        #
        # γ is grid convergence,
        # λ0 is longitude of UTM zone's central meridian,
        # φ, λ are latitude, longitude of point in question

        zone_center_longitude = (zone - 1) * 6 - 180 + 3
        gamma = math.atan(math.tan(math.radians(long - zone_center_longitude)) * math.sin(math.radians(lat)))
        return math.degrees(gamma)



