import json

import cv2
import multiprocessing
import time
import sys
from weather import Weather
import datetime
from path_reader import PathReader
from image import Image
from map_scaler import MapScaler
from map import Map
from pano_filter import PanoFilter
from gimbal_pitch_filter import GimbalPitchFilter
from infrared_rgb_sorter import InfraredRGBSorter
from OdmTaskManager import OdmTaskManager

class ImageMapper:
    def __init__(self, path_to_images, map_width_px=2048, map_height_px=2048, blending=0.7, optimize=True, max_gimbal_pitch_deviation=10, with_ODM=True):
        if path_to_images[-1] != "/":
            path_to_images += "/"
        self.path_to_images = path_to_images
        self.map_width_px = map_width_px
        self.map_height_px = map_height_px
        self.blending = blending
        self.optimize = optimize
        self.max_gimbal_pitch_deviation = max_gimbal_pitch_deviation
        self.with_ODM = with_ODM

        self.minimum_number_of_images = 4

        self.map_elements_IR = None
        self.map_elements_RGB = None
        self.final_map = None
        self.html_file_name = None
        self.corner_gps_right_top = None
        self.corner_gps_left_bottom = None
        self.middle_gps = None
        self.CONTAINED_DJI_INFRARED_IMAGES = False
        self.placeholder_map = None
        self.current_report_id = None

    @staticmethod
    def generate_images(image_paths):
        images = list()
        for path in image_paths:
            # print(path)
            images.append(Image(path))
        return images

    def set_processing_parameters(self, path_to_images=None, map_width_px=2048, map_height_px=2048, blending=0.7, optimize=True, max_gimbal_pitch_deviation=10, with_ODM=True):
        if path_to_images is not None:
            print("old Path to images: ", self.path_to_images)
            print("new Path to images: ", path_to_images)
            if path_to_images[-1] != "/":
                path_to_images += "/"
            self.path_to_images = path_to_images
        self.map_width_px = map_width_px
        self.map_height_px = map_height_px
        self.blending = blending
        self.optimize = optimize
        self.max_gimbal_pitch_deviation = max_gimbal_pitch_deviation
        self.with_ODM = with_ODM

    def preprocess_start(self, report_id):
        self.current_report_id = report_id

    def preprocess_read_selection(self, selection):
        if selection is None:
            image_paths = PathReader.read_path(self.path_to_images, ("DJI"), (".JPG", ".jpg"), sort=False)
        else:
            image_paths = PathReader.read_selection('./static', selection, ("DJI"), (".JPG", ".jpg"), sort=False)

            # Read all images and generate image objects using multiprocessing
        pool = multiprocessing.Pool(6)
        images = pool.map(ImageMapper.generate_images, [image_paths])[0]
        return images

    def preprocess_sort_images(self, images):
        images.sort(key=lambda x: x.get_exif_header().get_creation_time())
        return images

    def preprocess_filter_images(self, images):
        # Check if the minimum number of images is reached
        if len(images) < self.minimum_number_of_images:
            print("-Number of loaded image paths: ", len(images))
            return False

        # Filter images
        self.filtered_images = GimbalPitchFilter(89 - self.max_gimbal_pitch_deviation).filter(images)
        self.filtered_images = PanoFilter("pano").filter(self.filtered_images)

        # check wether infrared images are present
        self.__check_for_dji_infrared_images(self.filtered_images)

        if self.CONTAINED_DJI_INFRARED_IMAGES:
            (infrared_images, rgb_images) = InfraredRGBSorter().sort(self.filtered_images)
            self.map_scaler_IR = MapScaler(infrared_images, self.map_width_px, self.map_height_px)
            self.map_elements_IR = self.map_scaler_IR.get_map_elements()

            self.map_scaler_RGB = MapScaler(rgb_images, self.map_width_px, self.map_height_px)
            self.map_elements_RGB = self.map_scaler_RGB.get_map_elements()
            self.__calculate_gps_for_mapbox_plugin_initial_guess(self.map_scaler_RGB, self.map_elements_RGB)
        else:
            # Generate map elements using a MapScaler object
            self.map_scaler_RGB = MapScaler(self.filtered_images, self.map_width_px, self.map_height_px)
            self.map_elements_RGB = self.map_scaler_RGB.get_map_elements()
            self.__calculate_gps_for_mapbox_plugin_initial_guess(self.map_scaler_RGB, self.map_elements_RGB)
        return True


    # def preprocess_calculate_metadata(self):

    def preprocess_calculate_metadata(self):#, report_id, file_names):
        metadta_elements = self.map_elements_RGB
        if self.CONTAINED_DJI_INFRARED_IMAGES and metadta_elements is None:
            print("Map elements for RGB images are not available. Only IR Found")
            metadta_elements = self.map_elements_IR


        date = str(metadta_elements[0].get_image().get_exif_header().get_creation_time_str())
        try:
            self.location = str(metadta_elements[0].get_image().get_exif_header().get_gps().get_address())
        except:
            self.location = str("N/A")
            print("-Ignoring reverse adress search....")
            print("--", sys.exc_info()[0])

        flight_time_last = metadta_elements[-1].get_image().get_exif_header().get_creation_time()
        flight_time_first = metadta_elements[0].get_image().get_exif_header().get_creation_time()
        last = datetime.time(int(flight_time_last / 10000), int(flight_time_last % 10000 / 100), int(flight_time_last % 100))
        first = datetime.time(int(flight_time_first / 10000), int(flight_time_first % 10000 / 100), int(flight_time_first % 100))
        # flight_time = datetime.combine(datetime.date.min, last) - datetime.combine(datetime.date.min, first)

        flight_time_str = "long"  # str(flight_time).split(":")
        # flight_time_str = flight_time_str[-3] + " h : " + flight_time_str[-2] + " m : " + \
        #                        flight_time_str[-1] + " s"
        x_res = metadta_elements[0].get_image().get_width()
        y_res = metadta_elements[0].get_image().get_height()

        camera_properties = metadta_elements[0].get_image().get_exif_header().get_camera_properties()
        camera_model = camera_properties.get_model()
        camera_focal_length = camera_properties.get_focal_length()
        camera_fov = camera_properties.get_fov()
        camera_vertical_fov = camera_properties.get_vertical_fov()
        sensor_width, sensor_height = camera_properties.get_sensor_size()

        # print(self.area_k, self.avg_altitude, self.date, self.location, self.flight_time_str, self.camera_model, self.camera_fov)
        try:
            actual_weather = Weather(metadta_elements[0].get_image().get_exif_header().get_gps().get_latitude(),
                                     metadta_elements[0].get_image().get_exif_header().get_gps().get_longitude(),
                                     "e9d56399575efd5b03354fa77ef54abb")
            # print(weather_info_lst)
            temperature = actual_weather.get_temperature()
            humidity = actual_weather.get_humidity()
            altimeter = actual_weather.get_altimeter()
            wind_speed = actual_weather.get_wind_speed()
            visibility = actual_weather.get_visibility()
            wind_dir_degrees = actual_weather.get_wind_dir_degrees()
        except:
            print("-Ignoring weather details...")
            print("--", sys.exc_info())
            pass

        flight_data = []
        flight_data.append({"description": 'Date', "value": date})
        flight_data.append({"description": 'Time', "value": "time"})
        flight_data.append({"description": 'Location', "value": self.location})
        flight_data.append({"description": 'Area Covered', "value": self.map_scaler_RGB.get_area_in_m()})
        flight_data.append({"description": 'Flight Time', "value": flight_time_str})
        flight_data.append({"description": 'Processing Time', "value": "yyy"})
        flight_data.append({"description": 'Images', "value": len(metadta_elements)})
        flight_data.append({"description": 'Image Resolution', "value": str(x_res) + " x " + str(y_res)})
        flight_data.append({"description": 'Avg. Flight Height', "value": self.map_scaler_RGB.get_avg_altitude()})

        camera_specs = []
        camera_specs.append({"description": 'Camera Model', "value": camera_model})
        camera_specs.append({"description": 'Focal Length', "value": camera_focal_length})
        camera_specs.append({"description": 'Horizontal FOV', "value": camera_fov})
        camera_specs.append({"description": 'Vertical FOV', "value": camera_vertical_fov})
        camera_specs.append({"description": 'Sensor Size', "value": str(sensor_width) + " x " + str(sensor_height)})

        weather = []
        weather.append({"description": 'Temperature', "value": temperature})
        weather.append({"description": 'Humidity', "value": humidity})
        weather.append({"description": 'Air Preasure', "value": altimeter})
        weather.append({"description": 'Wind Speed', "value": wind_speed})
        weather.append({"description": 'Wind Direction', "value": wind_dir_degrees})
        weather.append({"description": 'Visibility', "value": visibility})

        lat1 = self.corner_gps_left_bottom.get_latitude()
        long1 = self.corner_gps_left_bottom.get_longitude()
        lat2 = self.corner_gps_right_top.get_latitude()
        long2 = self.corner_gps_right_top.get_longitude()
        latc = self.middle_gps.get_latitude()
        longc = self.middle_gps.get_longitude()
        bounds = [[lat1, long1], [lat2, long2]]

        # map = {
        #     "center": [latc, longc],
        #     "zoom": 18,
        #     "rgbMapFile": "default/MapRGBMissing.jpeg",
        #     "rgbMapBounds": bounds,
        #     "irMapFile": "default/MapIRMissing.jpeg",
        #     "irMapBounds": bounds,
        #     "ir_max_temp": 100,
        #     "ir_min_temp": 20,
        #     "ir_color_scheme": 3,
        # }


        map_rgb = {
            "center": [latc, longc],
            "zoom": 18,
            "file": "default/waiting.png",
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
            "file": "default/waiting.png",
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
            "file": "default/waiting.png",
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
            "file": "default/waiting.png",
            "bounds": bounds,
            "size": [1080, 1080],
            "image_coordinates": None,
            "ir": True,
            "odm": True,
            "name": "IR_ODM",
        }

        self.filenames_rgb = []
        self.filenames_ir = []
        for element in self.map_elements_RGB:
            self.filenames_rgb.append(element.get_image().get_image_path().split("static/", 1)[1])
        if self.CONTAINED_DJI_INFRARED_IMAGES:
            for element in self.map_elements_IR:
                self.filenames_ir.append(element.get_image().get_image_path().split("static/", 1)[1])

        return flight_data, camera_specs, weather, [map_rgb, map_ir, map_rgb_odm, map_ir_odm], self.filenames_rgb, self.filenames_ir


    # def map_images(self, report_id):
    #     if self.current_report_id != report_id:
    #         #self.pre_process_images()
    #         return None
    #     if self.map_elements_RGB is None:
    #         print("-No map elements found!")
    #         return None
    #
    #     maps = []
    #     maps.append(self.calculate_map_RGB())
    #     # map_file_name_RGB = "map.png"
    #     # self.save_map(str(report_id)+'/', map_file_name_RGB)
    #     # map_file_name_RGB  = "uploads/"+str(report_id)+"/"+map_file_name_RGB
    #     #
    #     # map_size_RGB = [self.cropped_map.shape[1], self.cropped_map.shape[0]]
    #     #
    #     #
    #     #
    #     # lat1 = self.corner_gps_left_bottom .get_latitude()
    #     # long1 = self.corner_gps_left_bottom.get_longitude()
    #     # lat2 = self.corner_gps_right_top .get_latitude()
    #     # long2 = self.corner_gps_right_top .get_longitude()
    #     # latc = self.middle_gps.get_latitude()
    #     # longc = self.middle_gps.get_longitude()
    #     # bounds = [[lat1, long1],[lat2, long2]]
    #     # bounds_ir = bounds
    #     #
    #     # map_file_name_IR = "default/MapIRMissing.jpeg"
    #     if self.CONTAINED_DJI_INFRARED_IMAGES:
    #         maps.append(self.calculate_map_IR())
    #     #     map_file_name_IR = "mapIR.png"
    #     #     self.save_map(str(report_id)+'/', map_file_name_IR)
    #     #     map_file_name_IR = "uploads/"+str(report_id)+"/"+map_file_name_IR
    #     #     lat1_ir = self.corner_gps_left_bottom.get_latitude()
    #     #     long1_ir = self.corner_gps_left_bottom.get_longitude()
    #     #     lat2_ir = self.corner_gps_right_top.get_latitude()
    #     #     long2_ir = self.corner_gps_right_top.get_longitude()
    #     #     latc_ir = self.middle_gps.get_latitude()
    #     #     longc_ir = self.middle_gps.get_longitude()
    #     #     bounds = [[lat1_ir, long1_ir], [lat2_ir, long2_ir]]
    #     #
    #     # map_size_IR = [self.cropped_map.shape[1], self.cropped_map.shape[0]]
    #
    #     # end_time = datetime.datetime.now().replace(microsecond=0)
    #     # self.__create_html("", map_file_name, end_time - start_time + filter_time, pano_files)
    #
    #
    #
    #
    #     # map = {
    #     #     "center": [latc, longc],
    #     #     "zoom": 18,
    #     #     "rgbMapFile": map_file_name_RGB,
    #     #     "rgbMapBounds": bounds,
    #     #     "rgbMapSize": map_size_RGB,
    #     #     "rgbCoordinates": self.extract_coordinates(self.map_elements_RGB, map_size_RGB[1]),
    #     #     "irMapFile": map_file_name_IR,
    #     #     "irMapBounds": bounds_ir,
    #     #     "irMapSize": map_size_IR,
    #     #     "irCoordinates": self.extract_coordinates(self.map_elements_RGB, map_size_IR[1]),
    #     #     "ir_max_temp": 100,
    #     #     "ir_min_temp": 20,
    #     #     "ir_color_scheme": 3,
    #     # }
    #     #
    #     # return map
    #
    def get_ir_settings(self):
        #TODO aus Meta Daten auslesen wenn vorhanden
        ir_settings = {
            "ir_max_temp": 100,
            "ir_min_temp": 20,
            "ir_color_scheme": 3,
        }
        return ir_settings

    def calculate_map_RGB(self, report_id):
        min_x, max_x, min_y, max_y = self.__calculate_map(self.map_scaler_RGB, self.map_elements_RGB)
        map = self.process_map(self.map_scaler_RGB, self.map_elements_RGB, min_x, max_x, min_y, max_y, False)
        return map

    def calculate_map_IR(self, report_id):
        min_x, max_x, min_y, max_y = self.__calculate_map(self.map_scaler_IR, self.map_elements_IR)
        map = self.process_map(self.map_scaler_IR, self.map_elements_IR, min_x, max_x, min_y, max_y, True)
        return map
    def process_map(self, map_scaler, map_elements, min_x, max_x, min_y, max_y, ir):
        map_file_name = "map_rgb.png" if not ir else "map_ir.png"
        map_file_path = "uploads/" + str(self.current_report_id) + "/" + map_file_name

        self.__calculate_gps_for_mapbox_plugin(map_elements, map_scaler, min_x, max_x, min_y, max_y)
        self.save_map(str(self.current_report_id) + '/', map_file_name)

        map_size = [self.cropped_map.shape[1], self.cropped_map.shape[0]]

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
            "file": map_file_path,
            "bounds": bounds,
            "size": map_size,
            "image_coordinates": self.extract_coordinates(map_elements, map_size[1]),
            "ir": ir,
            "odm": False,
            "name": "RGB" if not ir else "IR",
        }

        return map

    def __calculate_map(self, map_scaler, map_elements):
        map_offset = map_scaler.get_map_offset()
        # print(map_offset, "map offset")
        # self.__optimize_map_DEPRECATED()

        map_obj = Map(map_elements,
                      self.map_width_px + map_offset,
                      self.map_height_px + map_offset,
                      self.blending,
                      map_scaler.get_scale_px_per_m(),
                      self.optimize)

        print("-Creating map...             ")
        self.final_map = map_obj.create_map()
        self.cropped_map = map_obj.get_cropped_map()
        # self.__calculate_gps_for_mapbox_plugin(map_obj)
        if self.with_ODM and self.placeholder_map is None:
            self.placeholder_map = map_obj.generate_ODM_placeholder_map(self.path_to_images)
        return map_obj.get_min_and_max_coords()

    def save_map(self, relative_path, file_name):
        msg_str = relative_path + file_name
        path = self.path_to_images
        cv2.imwrite(path + msg_str, self.cropped_map)

        print("-Saved map under ", path + msg_str)

    def __check_for_dji_infrared_images(self, filtered_images):
        # (width_0, height_0) = filtered_images[0].get_exif_header().get_image_size()
        # (width_1, height_1) = filtered_images[1].get_exif_header().get_image_size()
        # if(width_0 != width_1 and height_0 != height_1):
        #     self.CONTAINED_DJI_INFRARED_IMAGES = True
        #     print("-Dataset contains infrared images...")
        # else:
        #     print("-Dataset does not contain infrared images...")

        #1. nach metadtaen zu IR suchen
        #2. nach Rbzw ir als namenssuffix suchen
        #3. nach unterschiedlichen bildgroessen suchen

        (width_0, height_0) = filtered_images[0].get_exif_header().get_image_size()
        for image in filtered_images:
            (width_1, height_1) = image.get_exif_header().get_image_size()
            if (width_0 != width_1 and height_0 != height_1):
                self.CONTAINED_DJI_INFRARED_IMAGES = True
                print("-Dataset contains infrared images...")
                return
        print("-Dataset does not contain infrared images...")

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
        self.middle_gps = map_scaler.get_middle_gps()

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
        self.middle_gps = map_scaler.get_middle_gps()

    def extract_coordinates(self, map_elements, map_height):
        new_coordinates = list()
        for map_element in map_elements:

            #image = map_element.get_image().get_matrix()
            rect = map_element.get_rotated_rectangle()
            coordinates = rect.get_contour().exterior.coords[:]

            tmp_coordinates = list()
            for coordinate in coordinates:
                x, y = coordinate
                tmp_coordinates.append(str(int(x)) + " " + str(int(map_height - y)))

            str_coordinates = ','.join(str(e) for e in tmp_coordinates)
            print("single coordinate:", str_coordinates)
            new_coordinates.append(str_coordinates)
        print("coordinates:", new_coordinates)
        return new_coordinates

    def generate_odm_orthophoto(self, container_port, image_size=0, ir=False):
        print("-Generating ODM orthophoto...")
        if not self.with_ODM:
            print("Error: ODM is not enabled for this dataset!")
            return

        options = {'feature-quality': 'medium', 'fast-orthophoto': True, 'auto-boundary': True, 'pc-ept': True,'cog': True}
        if ir:
            options = {'feature-quality': 'high', 'fast-orthophoto': True, 'auto-boundary': True, 'pc-ept': True,'cog': True}
        image_list = self.filenames_rgb.copy() if not ir else self.filenames_ir.copy()
        for j, image in enumerate(image_list):
            image_list[j] = "static/" + image
        print(image_list)
        taskmanager = OdmTaskManager(self.path_to_images + str(self.current_report_id) + "/", container_port)

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
                corner_gps_left_bottom = (bbox['minx'],bbox['miny'])
                corner_gps_right_top = (bbox['maxx'],bbox['maxy'])
                middle_gps = [(corner_gps_left_bottom[1] + corner_gps_right_top[1])/2, (corner_gps_left_bottom[0] + corner_gps_right_top[0])/2]
                bounds = [[corner_gps_left_bottom[1], corner_gps_left_bottom[0]], [corner_gps_right_top[1], corner_gps_right_top[0]]]
                print(corner_gps_left_bottom, corner_gps_right_top)

            im = cv2.imread("results/odm_orthophoto/odm_orthophoto.tif", cv2.IMREAD_UNCHANGED)
            map_size = [im.shape[1], im.shape[0]]
            target_path = self.path_to_images + str(self.current_report_id) + "/"
            filename = "odm_map.png" if not ir else "odm_map_ir.png"
            cv2.imwrite(target_path + filename, im)
            print("Orthophoto saved under", target_path+ filename)
            taskmanager.close()

            map = {
                "center": middle_gps,
                "zoom": 18,
                "file": 'uploads/'+ str(self.current_report_id) + "/" + filename,
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
                "size": [1080,1080],
                "image_coordinates": None,
                "ir": ir,
                "odm": True,
                "name": "RGB_ODM" if not ir else "IR_ODM",
            }
            print("Error: ODM task failed!")

        return map

    def generate_odm_orthophoto_all_at_once(self, container_port, image_size=0):
        options = [{'feature-quality': 'medium', 'fast-orthophoto': True, 'auto-boundary': True, 'pc-ept': True,'cog': True},
                   {'feature-quality': 'high', 'fast-orthophoto': True, 'auto-boundary': True, 'pc-ept': True,'cog': True}]
        image_lists = []
        maps = []
        image_lists.append(self.filenames_rgb.copy())
        if self.CONTAINED_DJI_INFRARED_IMAGES:
            image_lists.append(self.filenames_ir.copy())

        print(options)

        taskmanager = OdmTaskManager(self.path_to_images + str(self.current_report_id) + "/", container_port)

        #  run in loop over image_lists
        for i, list in enumerate(image_lists):

            for j, image in enumerate(list):
                list[j] = "static/" + image

            if(i == 0):
                taskmanager.set_images_scaled(list, image_size)
            else:
                taskmanager.set_images(list)

            taskmanager.run_task(options[i])

            while True:
                if not taskmanager.task_running():
                    break
                time.sleep(1)

            if taskmanager.task_complete:
                with open('results/odm_georeferencing/odm_georeferenced_model.info.json', 'r') as j:
                    contents = json.loads(j.read())
                    bbox = contents['stats']['bbox']['EPSG:4326']['bbox']
                    corner_gps_left_bottom = (bbox['minx'],bbox['miny'])
                    corner_gps_right_top = (bbox['maxx'],bbox['maxy'])
                #Todo, bounds irgendwie nutzen
                print(corner_gps_left_bottom, corner_gps_right_top)

                im = cv2.imread("results/odm_orthophoto/odm_orthophoto.tif", cv2.IMREAD_UNCHANGED)
                target_path = self.path_to_images + str(self.current_report_id) + "/"
                filename = "odm_map.png" if(i == 0) else "odm_map_ir.png"
                cv2.imwrite(target_path + filename, im)
                print("Orthophoto saved under", target_path+ filename)
                maps.append(target_path + filename)

        taskmanager.close()
        return maps