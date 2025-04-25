import json
import os.path as path

import shutil
import cv2
import time
import pyproj
import rasterio
from rasterio.transform import from_gcps
from rasterio.control import GroundControlPoint
from rasterio.transform import Affine
from rasterio.transform import from_bounds
import numpy as np

from .map import Map
from .gps import GPS
from .gimbal_pitch_filter import GimbalPitchFilter
from .map_scaler import MapScaler
from .map_scaler_improved import MapScalerImproved


class ImageMapper:
    def __init__(self, project_manager, webodm_manager, report_id, map_width_px=2048, map_height_px=2048, blending=0.7, optimize=True,
                 max_gimbal_pitch_deviation=10, with_odm=True, check_plausibility=True):
        self.project_manager = project_manager
        self.webodm_manager = webodm_manager
        self.report_id = report_id
        self.map_width_px = map_width_px
        self.map_height_px = map_height_px
        self.blending = blending
        self.optimize = optimize
        self.max_gimbal_pitch_deviation = max_gimbal_pitch_deviation
        self.with_odm = with_odm

        self.minimum_number_of_images = 3

        self.map_elements_IR = None
        self.map_elements_RGB = None
        self.map_scaler_IR = None
        self.map_scaler_RGB = None
        self.final_map = None
        self.corner_gps_right_top = None
        self.corner_gps_left_bottom = None
        self.middle_gps = None
        self.placeholder_map = None
        self.has_ir = False
        self.check_plausibility = check_plausibility

    def generate_map_elements_from_images(self, rgb_images=None, ir_images=None):
        if rgb_images is not None:
            self.map_scaler_RGB, self.map_elements_RGB = self.generate_map_elements_and_scaler(rgb_images)
        if ir_images is not None:
            self.map_scaler_IR, self.map_elements_IR = self.generate_map_elements_and_scaler(ir_images)

        if len(self.map_elements_IR) > 0:
            self.has_ir = True
        if len(self.map_elements_RGB) <= 0 and len(self.map_elements_IR) <= 0:
            if not self._generate_fallback_gps_from_images(rgb_images):
                if not self._generate_fallback_gps_from_images(ir_images):
                    self._generate_fallback_gps()
            print("No images found, using fallback gps", flush=True)
            return False

        if self.map_scaler_RGB is not None:
            self.__calculate_gps_for_mapbox_plugin_initial_guess(self.map_scaler_RGB, self.map_elements_RGB)
        elif self.map_scaler_IR is not None:
            self.__calculate_gps_for_mapbox_plugin_initial_guess(self.map_scaler_IR, self.map_elements_IR)

        return True


    def generate_map_elements_and_scaler(self, images):
        #print(images, flush=True)
        filtered_images = [image for image in images if image.get_exif_header().usable]
        if self.check_plausibility:
            filtered_images = self.filter_unplausible_images_by_time(filtered_images)
        filtered_images = GimbalPitchFilter(89 - self.max_gimbal_pitch_deviation).filter(filtered_images)


        if len(filtered_images) < self.minimum_number_of_images:
            print("Error: Not enough images for mapping!", flush=True)
            return None, []
        #map_scaler = MapScaler(filtered_images, self.map_width_px, self.map_height_px)
        map_scaler = MapScalerImproved(filtered_images, self.map_width_px, self.map_height_px)
        map_elements = map_scaler.get_map_elements()
        # print("map_scaler:", map_scaler, flush=True)
        return map_scaler, map_elements


    def generate_placeholder_maps(self):
        lat1 = self.corner_gps_left_bottom.get_latitude()
        long1 = self.corner_gps_left_bottom.get_longitude()
        lat2 = self.corner_gps_right_top.get_latitude()
        long2 = self.corner_gps_right_top.get_longitude()
        latc = self.middle_gps.get_latitude()
        longc = self.middle_gps.get_longitude()
        bounds = [[lat1, long1], [lat2, long2]]

        map_rgb = {
            "center": [latc, longc],
            "zoom": 18,
            "file": "./static/default/waiting.png",
            "bounds": bounds,
            "size": [1080, 1080],
            "image_coordinates": None,
            "ir": False,
            "odm": False,
            "name": "RGB",
        }

        map_ir = {
            "center": [latc, longc],
            "zoom": 18,
            "file": "./static/default/waiting.png",
            "bounds": bounds,
            "size": [1080, 1080],
            "image_coordinates": None,
            "ir": True,
            "odm": False,
            "name": "IR",
        }

        map_rgb_odm = {
            "center": [latc, longc],
            "zoom": 18,
            "file": "./static/default/waiting.png",
            "bounds": bounds,
            "size": [1080, 1080],
            "image_coordinates": None,
            "ir": False,
            "odm": True,
            "name": "RGB_ODM",
        }

        map_ir_odm = {
            "center": [latc, longc],
            "zoom": 18,
            "file": "./static/default/waiting.png",
            "bounds": bounds,
            "size": [1080, 1080],
            "image_coordinates": None,
            "ir": True,
            "odm": True,
            "name": "IR_ODM",
        }

        return [map_rgb, map_ir, map_rgb_odm, map_ir_odm]


    def calculate_map_RGB(self, report_id):
        self.map_elements_RGB = self.__calculate_map(self.map_scaler_RGB, self.map_elements_RGB, False)
        map_dict = self.process_map(self.map_scaler_RGB, self.map_elements_RGB, False)
        return map_dict

    def calculate_map_IR(self, report_id):
        # print("map scaler rgb & ir",self.map_scaler_IR, self.map_elements_IR, flush=True)
        self.map_elements_IR = self.__calculate_map(self.map_scaler_IR, self.map_elements_IR, True)
        map_dict = self.process_map(self.map_scaler_IR, self.map_elements_IR, True)
        return map_dict

    def process_map(self, map_scaler, map_elements, ir):
        map_file_name = "map_rgb.png" if not ir else "map_ir.png"
        map_file_path = path.join(self.project_manager.projects_path, str(self.report_id), map_file_name)
        self.__calculate_gps_for_mapbox_plugin(map_scaler)
        self.save_map(map_file_path)

        map_size = [self.cropped_map.shape[1], self.cropped_map.shape[0]]

        lat1 = self.corner_gps_left_bottom.get_latitude()
        long1 = self.corner_gps_left_bottom.get_longitude()
        lat2 = self.corner_gps_right_top.get_latitude()
        long2 = self.corner_gps_right_top.get_longitude()
        latc = self.middle_gps.get_latitude()
        longc = self.middle_gps.get_longitude()
        bounds = [[lat1, long1], [lat2, long2]]

        map_dict = {
            "center": [latc, longc],
            "zoom": 18,
            "file": map_file_path,
            "bounds": bounds,
            "bounds_corners":  map_scaler.map_bounds_gps["corners"],
            "size": map_size,
            "image_coordinates": self.extract_coordinates(map_elements, map_size[1]),
            "debug_coords_grid": map_scaler.generate_debug_coords_grid(),
            "ir": ir,
            "odm": False,
            "name": "RGB" if not ir else "IR",
        }

        #TODO save geo tif using rasterio
        self.__export_geotiff(map_dict["file"], map_dict["bounds_corners"])

        return map_dict

    def __export_geotiff(self, img_path, corners):
        """
        Converts a PNG image to a GeoTIFF with georeferencing.

        Parameters:
            img_path (str): Path to the PNG file.
            corners (list): List with four tuples (lat, lon), starting at bottom-left and going counter-clockwise.
        """
        geotiff_path = img_path.replace('.png', '.tif')
        print("Exporting GeoTIFF to ", geotiff_path, flush=True)

        # Open the PNG image using OpenCV
        img = cv2.imread(img_path, cv2.IMREAD_UNCHANGED)
        if img is None:
            raise ValueError("Error loading image. Check the file path.")

        # Ensure the image has 4 channels (RGBA)
        if img.shape[-1] == 3:
            img = cv2.cvtColor(img, cv2.COLOR_BGR2BGRA)
        elif img.shape[-1] == 4:
            img = cv2.cvtColor(img, cv2.COLOR_BGRA2RGBA)

        height, width = img.shape[:2]

        #get the smallest and largest lat and lon from the corners
        min_lon = min([corner[1] for corner in corners])
        min_lat = min([corner[0] for corner in corners])
        max_lon = max([corner[1] for corner in corners])
        max_lat = max([corner[0] for corner in corners])

        # Compute affine transformation
        transform = from_bounds(min_lon, min_lat, max_lon, max_lat, width, height)

        # Create GeoTIFF with affine transformation
        with rasterio.open(
                geotiff_path, 'w', driver='GTiff',
                height=height, width=width,
                count=4, dtype=img.dtype.name,  # Assuming RGBA
                crs='EPSG:4326',  # WGS84 coordinate system
                transform=transform,  # Now using a valid affine transform
                compress='DEFLATE',
                tiled=True,
        ) as dst:
            for band in range(4):  # RGBA bands
                dst.write(img[:, :, band], band + 1)

        print(f"GeoTIFF saved at {geotiff_path}")


    def __calculate_map(self, map_scaler, map_elements, ir):
        map_size = map_scaler.map_dimensions_px
        print("|| map_size", map_size, flush=True)
        self.map_width_px = map_size[0]
        self.map_height_px = map_size[1]

        map_obj = Map(map_elements,
                      self.map_width_px,
                      self.map_height_px,
                      self.blending,
                      map_scaler.meter_to_px_ratio,
                      self.optimize,
                      ir)

        print("-Creating map...             ")
        self.final_map = map_obj.create_map()
        self.cropped_map = map_obj.get_cropped_map()
        map_elements = map_obj.get_map_elements()
        return map_elements

    def save_map(self, save_path):
        # print("-Start saving map under ", save_path)
        cv2.imwrite(save_path, self.cropped_map)
        #print("-Saved map under ", save_path)

    def __calculate_gps_for_mapbox_plugin(self, map_scaler):
        self.corner_gps_right_top = GPS(0, map_scaler.map_bounds_gps["corners"][2][0],
                                        map_scaler.map_bounds_gps["corners"][2][1])

        self.corner_gps_left_bottom = GPS(0, map_scaler.map_bounds_gps["corners"][0][0],
                                          map_scaler.map_bounds_gps["corners"][0][1])

        self.middle_gps = GPS(0, map_scaler.map_bounds_gps["center"][0], map_scaler.map_bounds_gps["center"][1])

    def __calculate_gps_for_mapbox_plugin_initial_guess(self, map_scaler, map_elements):

        # origin_gps = map_elements[0].get_image().get_exif_header().get_gps()
        # origin_location = map_elements[0].get_rotated_rectangle().get_center()
        # # min_x, max_x, min_y, max_y = map_obj.get_min_and_max_coords()
        # min_x = float("inf")
        # min_y = float("inf")
        # max_x = float("-inf")
        # max_y = float("-inf")
        #
        # for map_element in map_elements:
        #     r = map_element.get_rotated_rectangle()
        #     coords_lst = r.get_multipoint()
        #     # print(coords_lst)
        #     for coord in coords_lst.geoms:
        #         x, y = coord.x, coord.y
        #         if (min_x > x):
        #             min_x = x
        #
        #         if (min_y > y):
        #             min_y = y
        #
        #         if (max_x < x):
        #             max_x = x
        #
        #         if (max_y < y):
        #             max_y = y
        # print(min_x, max_x, min_y, max_y)
        # corner_location_right_top = (max_x, max_y)
        # corner_location_left_bottom = (0, 0)
        self.corner_gps_right_top = GPS(0, map_scaler.map_bounds_gps["corners"][2][0], map_scaler.map_bounds_gps["corners"][2][1])

        self.corner_gps_left_bottom = GPS(0, map_scaler.map_bounds_gps["corners"][0][0], map_scaler.map_bounds_gps["corners"][0][1])
        # self.middle_gps = map_scaler.get_middle_gps()

        #calculate middle gps out of corners
        self.middle_gps = GPS(0, map_scaler.map_bounds_gps["center"][0], map_scaler.map_bounds_gps["center"][1])


    def extract_coordinates(self, map_elements, map_height):
        new_coordinates = list()
        for map_element in map_elements:

            # image = map_element.get_image().get_matrix()
            rect = map_element.get_projected_image_dims_px()
            coordinates = rect['corners']

            gps_coordinates = map_element.get_projected_image_dims_gps()['corners']

            tmp_coordinates = list()
            for coordinate in coordinates:
                x, y = coordinate
                tmp_coordinates.append(str(int(x)) + " " + str(int(map_height - y)))

            str_coordinates = ','.join(str(e) for e in tmp_coordinates)
            coodinate = {"coordinates_string": str_coordinates,
                         "coordinates_gps": gps_coordinates,
                         "file_name": map_element.get_image().get_image_path(),
                         "orientations": map_element.get_orientations(),}

            new_coordinates.append(coodinate)
        return new_coordinates

    def extract_gps_bounds(self):
        pass


    def generate_odm_orthophoto(self, filenames, image_size=0, ir=False):
        if not self.with_odm:
            print("Error: ODM is not enabled for this dataset!")
            return

        token = self.webodm_manager.authenticate()
        if token is None:
            print("Error: ODM is not enabled for this dataset!")
            map = self.generate_map_dict_from_odm_fail(ir)
            return map
        wo_project_id = self.webodm_manager.get_project_id(token, self.project_manager.get_project_name(self.report_id),
                                                           self.project_manager.get_project_description(self.report_id))
        if wo_project_id is None:
            wo_project_id = self.webodm_manager.create_project(token, self.project_manager.get_project_name(self.report_id),
                                                               self.project_manager.get_project_description(self.report_id))

        tmp_filenames = list()
        if image_size != 0:
            filenames = self.webodm_manager.scale_images(filenames, image_size)
            tmp_filenames = filenames

        r = self.webodm_manager.upload_and_process_images(token, wo_project_id, filenames, fast_orthophoto=True)
        task_id = r['id']
        failed = False
        while True:
            #print("waiting for ODM")
            time.sleep(3)

            status = self.webodm_manager.get_task_data_by_key(token, wo_project_id, task_id, 'status')
            if status == 30:
                print("Error: ODM task failed!", self.webodm_manager.get_task_data_by_key(token, wo_project_id, task_id, 'last_error'))
                failed = True
                break

            if status == 50:
                print("Error: ODM task canceled!", self.webodm_manager.get_task_data_by_key(token, wo_project_id, task_id, 'last_error'))
                failed = True
                break

            progress = self.webodm_manager.get_task_data_by_key(token, wo_project_id, task_id, 'running_progress')
            if progress >= 1.0:
                break

        self.webodm_manager.clean_up(tmp_filenames)

        if failed:
            map = self.generate_map_dict_from_odm_fail(ir)
            return map

        results_folder = self.webodm_manager.download_assets_from_task(token, wo_project_id, task_id,
                                                                       path.join(self.project_manager.projects_path,
                                                                                 str(self.report_id)))

        if results_folder is None:
            map = self.generate_map_dict_from_odm_fail(ir)
            return map

        map = self.generate_map_dict_from_odm_results(results_folder, ir)

        return map

    def generate_map_dict_from_odm_results(self, results_folder, ir=False):
        bounds = None
        middle_gps = None
        georef_file = 'odm_georeferencing/odm_georeferenced_model.info.json'
        with open(path.join(results_folder, georef_file), 'r') as j:
            contents = json.loads(j.read())
            bbox = contents['stats']['bbox']['EPSG:4326']['bbox']
            corner_gps_left_bottom = (bbox['minx'], bbox['miny'])
            corner_gps_right_top = (bbox['maxx'], bbox['maxy'])
            middle_gps = [(corner_gps_left_bottom[1] + corner_gps_right_top[1]) / 2,
                          (corner_gps_left_bottom[0] + corner_gps_right_top[0]) / 2]
            bounds = [[corner_gps_left_bottom[1], corner_gps_left_bottom[0]],
                      [corner_gps_right_top[1], corner_gps_right_top[0]]]

            bounds_corners_odm = contents['stats']['bbox']['EPSG:4326']['boundary']['coordinates'][0]
            bounds_corners = [[coord[1], coord[0]] for coord in bounds_corners_odm]
            #swap index 1 and 3
            bounds_corners[1], bounds_corners[3] = bounds_corners[3], bounds_corners[1]

            # print(corner_gps_left_bottom, corner_gps_right_top)


        map_file = 'odm_orthophoto/odm_orthophoto.tif'
        im = cv2.imread(path.join(results_folder, map_file), cv2.IMREAD_UNCHANGED)
        map_size = [im.shape[1], im.shape[0]]
        filename = "odm_map.png" if not ir else "odm_map_ir.png"
        save_path = path.join(self.project_manager.projects_path, str(self.report_id), filename)
        cv2.imwrite(save_path, im)
        #print("Orthophoto saved under", save_path)

        bounds_corners = []
        dat = rasterio.open(path.join(results_folder, map_file))
        utm_bounds = dat.bounds
        utm_crs = dat.crs
        print("UTM bounds: ", utm_bounds, flush=True)
        print("UTM crs: ", utm_crs, flush=True)
        print("path of geotif from webodm: ", path.join(results_folder, map_file), flush=True)


        transformer = pyproj.Transformer.from_crs(utm_crs, "EPSG:4326")
        top_left = transformer.transform(utm_bounds.left, utm_bounds.top)
        top_right = transformer.transform(utm_bounds.right, utm_bounds.top)
        bottom_right = transformer.transform(utm_bounds.right, utm_bounds.bottom)
        bottom_left = transformer.transform(utm_bounds.left, utm_bounds.bottom)

        print("UTM bounds converted: ", top_left, top_right, bottom_left, bottom_right, flush=True)

        map = {
            "center": middle_gps,
            "zoom": 18,
            "file": save_path,
            "bounds": [top_left, bottom_right],
            "bounds_corners": [bottom_left, bottom_right, top_right, top_left],
            "size": map_size,
            "image_coordinates": None,
            "ir": ir,
            "odm": True,
            "name": "RGB_ODM" if not ir else "IR_ODM",
        }

        self.__move_and_rename_geotif(path.join(results_folder, map_file), path.join(self.project_manager.projects_path, str(self.report_id), filename.replace('.png', '.tif')))

        return map
    def __move_and_rename_geotif(self, src, dst):
        shutil.move(src, dst)
        print("Moved geotif to ", dst, flush=True)

    def generate_map_dict_from_odm_fail(self, ir=False):
        lat1 = self.corner_gps_left_bottom.get_latitude()
        long1 = self.corner_gps_left_bottom.get_longitude()
        lat2 = self.corner_gps_right_top.get_latitude()
        long2 = self.corner_gps_right_top.get_longitude()
        latc = self.middle_gps.get_latitude()
        longc = self.middle_gps.get_longitude()
        bounds = [[lat1, long1], [lat2, long2]]

        map = {
            "center": [latc, longc],
            "zoom": 18,
            "file": "./static/default/ODMFehler.png",
            "bounds": bounds,
            "size": [1080, 1080],
            "image_coordinates": None,
            "ir": ir,
            "odm": True,
            "name": "RGB_ODM" if not ir else "IR_ODM",
        }
        print("Error: ODM task failed!")

        return map


    def get_ir_settings(self):
        # TODO aus Meta Daten auslesen wenn vorhanden
        ir_settings = {
            "ir_max_temp": 100,
            "ir_min_temp": 20,
            "ir_color_scheme": 3,
        }
        return ir_settings

    def generate_error_map(self, images, ir=False):
        try:
            if len(images) > self.minimum_number_of_images:
                map_scaler = MapScaler(images, self.map_width_px, self.map_height_px)
                map_elements = map_scaler.get_map_elements()
                self.__calculate_gps_for_mapbox_plugin_initial_guess(map_scaler, map_elements)
        except Exception as e:
            print("Error: Generating with backup gps bounds - error:", e)


        lat1 = self.corner_gps_left_bottom.get_latitude()
        long1 = self.corner_gps_left_bottom.get_longitude()
        lat2 = self.corner_gps_right_top.get_latitude()
        long2 = self.corner_gps_right_top.get_longitude()
        latc = self.middle_gps.get_latitude()
        longc = self.middle_gps.get_longitude()
        bounds = [[lat1, long1], [lat2, long2]]

        map_dict = {
            "center": [latc, longc],
            "zoom": 18,
            "file": "./static/default/MappingFailed.png",
            "bounds": bounds,
            "size": [1080, 1080],
            "image_coordinates": None,
            "ir": ir,
            "odm": False,
            "name": "RGB" if not ir else "IR",
        }

        return map_dict

    def _generate_fallback_gps(self):
        self.corner_gps_left_bottom = GPS(0, 51.57326, 7.02768)
        self.corner_gps_right_top = GPS(0, 51.57475, 7.02885)
        self.middle_gps = GPS(0, 51.57399, 7.02826)

    def _generate_fallback_gps_from_images(self, images):
        print("Fallback GPS from images", flush=True)
        try:
            lat_max = 999999999.9
            lat_min = -999999999.9
            long_max = 999999999.9
            long_min = -999999999.9
            for image in images:
                try:
                    gps = image.get_exif_header().get_gps()
                    lat = gps.get_latitude()
                    long = gps.get_longitude()
                    if lat > lat_min:
                        lat_min = lat
                    if lat < lat_max:
                        lat_max = lat
                    if long > long_min:
                        long_min = long
                    if long < long_max:
                        long_max = long
                except:
                    continue
            #print("Fallback GPS: ", lat_min, long_min, lat_max, long_max)
            if lat_min == 999999999.9 or long_min == 999999999.9 or lat_max == 0.0 or long_max == 0.0:
                return False
            self.corner_gps_left_bottom = GPS(0, lat_min, long_min)
            self.corner_gps_right_top = GPS(0, lat_max, long_max)
            self.middle_gps = GPS(0, (lat_max + lat_min) / 2, (long_max + long_min) / 2)
            print("Fallback GPS: ", self.corner_gps_left_bottom, self.corner_gps_right_top, self.middle_gps, flush=True)
            return True
        except:
            print("Error: Fallback GPS failed!")
            return False

    def filter_unplausible_images_by_time(self, filtered_images):
        if len(filtered_images) < 3:
            return []
        time_list = [image.get_exif_header().get_creation_time() for image in filtered_images]

        time_diff = [time_list[i+1] - time_list[i] for i in range(len(time_list)-1)]
        #make a copy of the time_diff list and sort it
        time_diff_sorted = time_diff.copy()
        time_diff_sorted.sort()
        median_time = time_diff_sorted[len(time_diff_sorted)//2]

        list_of_connected_flights = []
        plausible_flight = []

        for i in range(len(filtered_images)-1):

            plausible_flight.append(filtered_images[i])
            compare_time = 4*median_time if 4*median_time > 45.0 else 45.0
            #print("Time diff: ", time_diff[i], " Median time: ", median_time, " Compare time: ", compare_time, flush=True)
            if time_diff[i] > compare_time:
                print("~p not plausible flight! with time diff: ", time_diff[i], " and median time: ", median_time, flush=True)
                list_of_connected_flights.append(plausible_flight.copy())
                plausible_flight = []

        plausible_flight.append(filtered_images[-1])

        list_of_connected_flights.append(plausible_flight)
        lengths = [len(flight) for flight in list_of_connected_flights]
        print("Connected flights with n images: ", lengths, flush=True)

        return max(list_of_connected_flights, key=len)








