import json
import os.path as path

import cv2
import time

from map import Map
from OdmTaskManager import OdmTaskManager
from gps import GPS
from gimbal_pitch_filter import GimbalPitchFilter
from map_scaler import MapScaler


class ImageMapper:
    def __init__(self, project_manager, report_id, map_width_px=2048, map_height_px=2048, blending=0.7, optimize=True,
                 max_gimbal_pitch_deviation=10, with_odm=True):
        self.project_manager = project_manager
        self.report_id = report_id
        self.map_width_px = map_width_px
        self.map_height_px = map_height_px
        self.blending = blending
        self.optimize = optimize
        self.max_gimbal_pitch_deviation = max_gimbal_pitch_deviation
        self.with_odm = with_odm

        self.minimum_number_of_images = 2

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
            return False

        if self.map_scaler_RGB is not None:
            self.__calculate_gps_for_mapbox_plugin_initial_guess(self.map_scaler_RGB, self.map_elements_RGB)
        elif self.map_scaler_IR is not None:
            self.__calculate_gps_for_mapbox_plugin_initial_guess(self.map_scaler_IR, self.map_elements_IR)

        return True


    def generate_map_elements_and_scaler(self, images):
        filtered_images = GimbalPitchFilter(89 - self.max_gimbal_pitch_deviation).filter(images)
        if len(filtered_images) < self.minimum_number_of_images:
            return None, []
        map_scaler = MapScaler(filtered_images, self.map_width_px, self.map_height_px)
        map_elements = map_scaler.get_map_elements()
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
        (min_x, max_x, min_y, max_y), self.map_elements_RGB = self.__calculate_map(self.map_scaler_RGB,
                                                                                   self.map_elements_RGB)
        map_dict = self.process_map(self.map_scaler_RGB, self.map_elements_RGB, min_x, max_x, min_y, max_y, False)
        return map_dict

    def calculate_map_IR(self, report_id):
        (min_x, max_x, min_y, max_y), self.map_elements_IR = self.__calculate_map(self.map_scaler_IR,
                                                                                  self.map_elements_IR)
        map_dict = self.process_map(self.map_scaler_IR, self.map_elements_IR, min_x, max_x, min_y, max_y, True)
        return map_dict

    def process_map(self, map_scaler, map_elements, min_x, max_x, min_y, max_y, ir):
        map_file_name = "map_rgb.png" if not ir else "map_ir.png"
        map_file_path = path.join(self.project_manager.projects_path, str(self.report_id), map_file_name)
        self.__calculate_gps_for_mapbox_plugin(map_elements, map_scaler, min_x, max_x, min_y, max_y)
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
            "size": map_size,
            "image_coordinates": self.extract_coordinates(map_elements, map_size[1]),
            "ir": ir,
            "odm": False,
            "name": "RGB" if not ir else "IR",
        }

        return map_dict

    def __calculate_map(self, map_scaler, map_elements):
        map_offset = map_scaler.get_map_offset()

        map_obj = Map(map_elements,
                      self.map_width_px + map_offset,
                      self.map_height_px + map_offset,
                      self.blending,
                      map_scaler.get_scale_px_per_m(),
                      self.optimize)

        print("-Creating map...             ")
        self.final_map = map_obj.create_map()
        self.cropped_map = map_obj.get_cropped_map()
        map_elements = map_obj.get_map_elements()
        return map_obj.get_min_and_max_coords(), map_elements

    def save_map(self, save_path):
        print("-Start saving map under ", save_path)
        cv2.imwrite(save_path, self.cropped_map)
        print("-Saved map under ", save_path)

    def __calculate_gps_for_mapbox_plugin(self, map_elements, map_scaler, min_x, max_x, min_y, max_y):
        origin_gps = map_elements[0].get_image().get_exif_header().get_gps()
        origin_location = map_elements[0].get_rotated_rectangle().get_center()
        corner_location_right_top = (max_x, max_y)
        corner_location_left_bottom = (0, 0)
        self.corner_gps_right_top = map_scaler.calculate_corner_gps_coordinates(origin_gps,
                                                                                origin_location,
                                                                                corner_location_right_top)

        self.corner_gps_left_bottom = map_scaler.calculate_corner_gps_coordinates(origin_gps,
                                                                                  origin_location,
                                                                                  corner_location_left_bottom)
        self.middle_gps = self.middle_gps = GPS(self.corner_gps_left_bottom.altitude,
                                                self.corner_gps_left_bottom.get_latitude() +
                                                (self.corner_gps_right_top.get_latitude() -
                                                 self.corner_gps_left_bottom.get_latitude()) / 2,
                                                self.corner_gps_left_bottom.get_longitude() +
                                                (self.corner_gps_right_top.get_longitude() -
                                                 self.corner_gps_left_bottom.get_longitude()) / 2)


    def __calculate_gps_for_mapbox_plugin_initial_guess(self, map_scaler, map_elements):

        origin_gps = map_elements[0].get_image().get_exif_header().get_gps()
        origin_location = map_elements[0].get_rotated_rectangle().get_center()
        # min_x, max_x, min_y, max_y = map_obj.get_min_and_max_coords()
        min_x = float("inf")
        min_y = float("inf")
        max_x = float("-inf")
        max_y = float("-inf")

        for map_element in map_elements:
            r = map_element.get_rotated_rectangle()
            coords_lst = r.get_multipoint()
            # print(coords_lst)
            for coord in coords_lst.geoms:
                x, y = coord.x, coord.y
                if (min_x > x):
                    min_x = x

                if (min_y > y):
                    min_y = y

                if (max_x < x):
                    max_x = x

                if (max_y < y):
                    max_y = y
        # print(min_x, max_x, min_y, max_y)
        corner_location_right_top = (max_x, max_y)
        corner_location_left_bottom = (0, 0)
        self.corner_gps_right_top = map_scaler.calculate_corner_gps_coordinates(origin_gps,
                                                                                     origin_location,
                                                                                     corner_location_right_top)

        self.corner_gps_left_bottom = map_scaler.calculate_corner_gps_coordinates(origin_gps,
                                                                                       origin_location,
                                                                                       corner_location_left_bottom)
        # self.middle_gps = map_scaler.get_middle_gps()

        #calculate middle gps out of corners
        self.middle_gps = GPS(self.corner_gps_left_bottom.altitude, self.corner_gps_left_bottom.get_latitude() +
            (self.corner_gps_right_top.get_latitude() - self.corner_gps_left_bottom.get_latitude()) / 2,
            self.corner_gps_left_bottom.get_longitude() +
            (self.corner_gps_right_top.get_longitude() - self.corner_gps_left_bottom.get_longitude()) / 2)


    def extract_coordinates(self, map_elements, map_height):
        new_coordinates = list()
        for map_element in map_elements:

            # image = map_element.get_image().get_matrix()
            rect = map_element.get_rotated_rectangle()
            coordinates = rect.get_contour().exterior.coords[:]

            tmp_coordinates = list()
            for coordinate in coordinates:
                x, y = coordinate
                tmp_coordinates.append(str(int(x)) + " " + str(int(map_height - y)))

            str_coordinates = ','.join(str(e) for e in tmp_coordinates)
            coodinate = {"coordinates_string": str_coordinates,
                         "file_name": map_element.get_image().get_image_path()}

            new_coordinates.append(coodinate)
        return new_coordinates

    def generate_odm_orthophoto(self, container_port, filenames, image_size=0, ir=False):
        print("-Generating ODM orthophoto...")
        if not self.with_odm:
            print("Error: ODM is not enabled for this dataset!")
            return

        options = {'feature-quality': 'medium', 'fast-orthophoto': True, 'auto-boundary': True, 'pc-ept': True,
                   'cog': True}
        if ir:
            options = {'feature-quality': 'high', 'fast-orthophoto': True, 'auto-boundary': True, 'pc-ept': True,
                       'cog': True}
        image_list = filenames.copy()  # self.filenames_rgb.copy() if not ir else self.filenames_ir.copy()
        for j, image in enumerate(image_list):
            image_list[j] = "static/" + image
        # print(image_list)
        taskmanager = OdmTaskManager(path.join(self.project_manager.projects_path, str(self.report_id)), container_port)

        if image_size != 0:
            taskmanager.set_images_scaled(image_list, image_size)
        else:
            taskmanager.set_images(image_list)

        taskmanager.run_task(options)

        while True:
            if not taskmanager.task_running():
                break
            time.sleep(1)

        if taskmanager.task_complete:
            bounds = None
            middle_gps = None
            with open('results/odm_georeferencing/odm_georeferenced_model.info.json', 'r') as j:
                contents = json.loads(j.read())
                bbox = contents['stats']['bbox']['EPSG:4326']['bbox']
                corner_gps_left_bottom = (bbox['minx'], bbox['miny'])
                corner_gps_right_top = (bbox['maxx'], bbox['maxy'])
                middle_gps = [(corner_gps_left_bottom[1] + corner_gps_right_top[1]) / 2,
                              (corner_gps_left_bottom[0] + corner_gps_right_top[0]) / 2]
                bounds = [[corner_gps_left_bottom[1], corner_gps_left_bottom[0]],
                          [corner_gps_right_top[1], corner_gps_right_top[0]]]
                # print(corner_gps_left_bottom, corner_gps_right_top)

            im = cv2.imread("results/odm_orthophoto/odm_orthophoto.tif", cv2.IMREAD_UNCHANGED)
            map_size = [im.shape[1], im.shape[0]]
            filename = "odm_map.png" if not ir else "odm_map_ir.png"
            save_path = path.join(self.project_manager.projects_path, str(self.report_id), filename)
            cv2.imwrite(save_path, im)
            print("Orthophoto saved under", save_path)
            taskmanager.close()

            map = {
                "center": middle_gps,
                "zoom": 18,
                "file": 'uploads/' + str(self.report_id) + "/" + filename,
                "bounds": bounds,
                "size": map_size,
                "image_coordinates": None,
                "ir": ir,
                "odm": True,
                "name": "RGB_ODM" if not ir else "IR_ODM",
            }

        else:
            taskmanager.close()

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
                "file": "default/ODMFehler.png",
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
        if len(images) > self.minimum_number_of_images:
            map_scaler = MapScaler(images, self.map_width_px, self.map_height_px)
            map_elements = map_scaler.get_map_elements()
            self.__calculate_gps_for_mapbox_plugin_initial_guess(map_scaler, map_elements)

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
            "file": "default/MappingFailed.png",
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
        try:
            lat_max = 999999999.9
            lat_min = 0.0
            long_max = 999999999.9
            long_min = 0.0
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
            print("Fallback GPS: ", lat_min, long_min, lat_max, long_max)
            if lat_min == 999999999.9 or long_min == 999999999.9 or lat_max == 0.0 or long_max == 0.0:
                return False
            self.corner_gps_left_bottom = GPS(0, lat_min, long_min)
            self.corner_gps_right_top = GPS(0, lat_max, long_max)
            self.middle_gps = GPS(0, (lat_max + lat_min) / 2, (long_max + long_min) / 2)
            return True
        except:
            print("Error: Fallback GPS failed!")
            return False
