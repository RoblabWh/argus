import json

import cv2
import multiprocessing
import time
import sys

from imageTypeSorter import ImageTypeSorter
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
from gps import GPS


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
        self.map_scaler_RGB = None
        self.map_scaler_IR = None
        self.final_map = None
        self.html_file_name = None
        self.corner_gps_right_top = None
        self.corner_gps_left_bottom = None
        self.middle_gps = None
        self.CONTAINED_DJI_INFRARED_IMAGES = False
        self.placeholder_map = None
        self.current_report_id = None
        self.contains_panos = False
        self.unfiltered_sorted_images = []

    @staticmethod
    def generate_images(image_paths):
        images = list()
        for path in image_paths:
            # print(path)
            images.append(Image(path))
        return images

    def set_processing_parameters(self, path_to_images=None, map_width_px=2048, map_height_px=2048, blending=0.7, optimize=True, max_gimbal_pitch_deviation=10, with_ODM=True):
        if path_to_images is not None:
            # print("old Path to images: ", self.path_to_images)
            # print("new Path to images: ", path_to_images)
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

    def chunks(self, lst, n):
        """Yield successive n-sized chunks from lst."""
        for i in range(0, len(lst), n):
            yield lst[i:i + n]

    def preprocess_read_selection(self, selection):
        if selection is None:
            image_paths = PathReader.read_path(self.path_to_images, ("DJI"), (".JPG", ".jpg"), sort=False)
        else:
            image_paths = PathReader.read_selection('./static', selection, ("DJI"), (".JPG", ".jpg"), sort=False)

        nmbr_of_processes = 6
        image_paths_list = list(self.chunks(image_paths,  int(len(image_paths)/nmbr_of_processes)+1))

            # Read all images and generate image objects using multiprocessing
        pool = multiprocessing.Pool(nmbr_of_processes)
        time_before_loading = time.time()
        # image_paths
        images_lists = pool.map(ImageMapper.generate_images, image_paths_list)
        images = []
        for lst in images_lists:
            images += (lst)

        time_after_loading = time.time()
        # print("LOADING TIME SUMMARY: ", str(time_after_loading - time_before_loading))
        return images

    def preprocess_sort_images(self, images):
        images.sort(key=lambda x: x.get_exif_header().get_creation_time())
        return images

    def preprocess_filter_images(self, images):
        # Check if the minimum number of images is reached
        if len(images) < self.minimum_number_of_images:
            # print("-Number of loaded image paths: ", len(images))
            return False

        # filter panoramas
        imageSorter = ImageTypeSorter()
        panos, images = imageSorter.filter_panos(images)
        if len(panos) > 0:
            self.contains_panos = True
            self.panos = panos


        self.unfiltered_sorted_images = images.copy()

        print("start building couples_path_list")
        self.couples_path_list = InfraredRGBSorter().build_couples_path_list_from_scratch(self.unfiltered_sorted_images)
        print("couples_path_list: ", self.couples_path_list)


        # Filter images
        self.filtered_images = GimbalPitchFilter(89 - self.max_gimbal_pitch_deviation).filter(images)
        self.filtered_images = PanoFilter("pano").filter(self.filtered_images)


        self.CONTAINED_DJI_INFRARED_IMAGES = imageSorter.check_for_IR(self.filtered_images)
        # self.__check_for_dji_infrared_images(self.filtered_images)

        if self.CONTAINED_DJI_INFRARED_IMAGES:
            if len(self.filtered_images) <= 1:
                self.map_scaler_RGB = None
                self.map_elements_RGB = None
            else:
                (infrared_images, rgb_images) = InfraredRGBSorter().sort(self.filtered_images)
                self.map_scaler_IR = MapScaler(infrared_images, self.map_width_px, self.map_height_px)
                self.map_elements_IR = self.map_scaler_IR.get_map_elements()

                self.map_scaler_RGB = MapScaler(rgb_images, self.map_width_px, self.map_height_px)
                self.map_elements_RGB = self.map_scaler_RGB.get_map_elements()
                self.__calculate_gps_for_mapbox_plugin_initial_guess(self.map_scaler_RGB, self.map_elements_RGB)
        else:
            # Generate map elements using a MapScaler object
            if len(self.filtered_images) <= 1:
                self.map_scaler_RGB = None
                self.map_elements_RGB = None
            else:
                self.map_scaler_RGB = MapScaler(self.filtered_images, self.map_width_px, self.map_height_px)
                self.map_elements_RGB = self.map_scaler_RGB.get_map_elements()
                self.__calculate_gps_for_mapbox_plugin_initial_guess(self.map_scaler_RGB, self.map_elements_RGB)
        return True

    def get_panos(self):
        panos = []
        if self.contains_panos:
            for pano in self.panos:
                panos.append(pano.get_exif_header().pano_data)

        return panos


    def preprocess_calculate_metadata(self):#, report_id, file_names):
        metadta_elements = self.map_elements_RGB
        if self.CONTAINED_DJI_INFRARED_IMAGES and metadta_elements is None:
            print("Map elements for RGB images are not available. Only IR Found")
            metadta_elements = self.map_elements_IR

        if metadta_elements is None:
            firstImage = self.unfiltered_sorted_images[0]
            lastImage = self.unfiltered_sorted_images[-1]
        else:
            firstImage = metadta_elements[0].get_image()
            lastImage = metadta_elements[-1].get_image()

        date = str(firstImage.get_exif_header().get_creation_time_str())
        try:
            self.location = str(firstImage.get_exif_header().get_gps().get_address())
        except:
            self.location = str("N/A")
            print("-Ignoring reverse adress search....")
            print("--", sys.exc_info()[0])

        flight_time_last = lastImage.get_exif_header().get_creation_time()
        flight_time_first = firstImage.get_exif_header().get_creation_time()
        last = datetime.time(int(flight_time_last / 10000), int(flight_time_last % 10000 / 100), int(flight_time_last % 100))
        first = datetime.time(int(flight_time_first / 10000), int(flight_time_first % 10000 / 100), int(flight_time_first % 100))
        # flight_time = datetime.combine(datetime.date.min, last) - datetime.combine(datetime.date.min, first)

        flight_time_str = "long"  # str(flight_time).split(":")
        # flight_time_str = flight_time_str[-3] + " h : " + flight_time_str[-2] + " m : " + \
        #                        flight_time_str[-1] + " s"
        x_res = firstImage.get_width()
        y_res = firstImage.get_height()

        camera_properties = firstImage.get_exif_header().get_camera_properties()
        camera_model = camera_properties.get_model()
        camera_focal_length = camera_properties.get_focal_length()
        camera_fov = camera_properties.get_fov()
        camera_vertical_fov = camera_properties.get_vertical_fov()
        sensor_width, sensor_height = camera_properties.get_sensor_size()

        # print(self.area_k, self.avg_altitude, self.date, self.location, self.flight_time_str, self.camera_model, self.camera_fov)
        try:
            actual_weather = Weather(firstImage.get_exif_header().get_gps().get_latitude(),
                                     firstImage.get_exif_header().get_gps().get_longitude(),
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

        if self.map_scaler_RGB is not None:
            area_k = self.map_scaler_RGB.get_area_in_m()
            avg_altitude = self.map_scaler_RGB.get_avg_altitude()
        elif self.map_scaler_IR is not None:
            area_k = self.map_scaler_IR.get_area_in_m()
            avg_altitude = self.map_scaler_IR.get_avg_altitude()
        else:
            area_k = "only caluclated with fast mapping"
            avg_altitude = "only caluclated with fast mapping"


        flight_data = []
        flight_data.append({"description": 'Date', "value": date})
        flight_data.append({"description": 'Time', "value": "time"})
        flight_data.append({"description": 'Location', "value": self.location})
        flight_data.append({"description": 'Area Covered', "value": area_k})
        flight_data.append({"description": 'Flight Time', "value": flight_time_str})
        flight_data.append({"description": 'Processing Time', "value": "yyy"})
        flight_data.append({"description": 'Images', "value": len(self.unfiltered_sorted_images)})
        flight_data.append({"description": 'Image Resolution', "value": str(x_res) + " x " + str(y_res)})
        flight_data.append({"description": 'Avg. Flight Height', "value": avg_altitude})

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



        # self.filenames_rgb = []
        # self.filenames_ir = []
        # for element in self.map_elements_RGB:
        #     self.filenames_rgb.append(element.get_image().get_image_path().split("static/", 1)[1])
        # if self.CONTAINED_DJI_INFRARED_IMAGES:
        #     for element in self.map_elements_IR:
        #         self.filenames_ir.append(element.get_image().get_image_path().split("static/", 1)[1])

        return flight_data, camera_specs, weather, #self.filenames_rgb, self.filenames_ir

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

        return [map_rgb, map_ir, map_rgb_odm, map_ir_odm]

    def generate_flight_profiles(self):
        # self.unfiltered_sorted_images = fe
        pass


    def get_ir_settings(self):
        #TODO aus Meta Daten auslesen wenn vorhanden
        ir_settings = {
            "ir_max_temp": 100,
            "ir_min_temp": 20,
            "ir_color_scheme": 3,
        }
        return ir_settings


    def calculate_map_RGB(self, report_id):
        (min_x, max_x, min_y, max_y), self.map_elements_RGB = self.__calculate_map(self.map_scaler_RGB, self.map_elements_RGB)
        map = self.process_map(self.map_scaler_RGB, self.map_elements_RGB, min_x, max_x, min_y, max_y, False)
        return map


    def calculate_map_IR(self, report_id):
        (min_x, max_x, min_y, max_y), self.map_elements_IR = self.__calculate_map(self.map_scaler_IR, self.map_elements_IR)
        map = self.process_map(self.map_scaler_IR, self.map_elements_IR, min_x, max_x, min_y, max_y, True)
        return map


    def process_map(self, map_scaler, map_elements, min_x, max_x, min_y, max_y, ir):
        map_file_name = "map_rgb.png" if not ir else "map_ir.png"
        map_file_path = "uploads/" + str(self.current_report_id) + "/" + map_file_name
        # print("MAPPROCESS; min_x: " + str(min_x) + " max_x: " + str(max_x) + " min_y: " + str(min_y) + " max_y: " + str(max_y))
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
        timaa = time.time()
        self.final_map = map_obj.create_map()
        timeb = time.time()
        self.cropped_map = map_obj.get_cropped_map()
        timec = time.time()
        # print("Map creation time: ", timeb - timaa)
        # print("Map cropping time: ", timec - timeb)
        map_elements = map_obj.get_map_elements()
        # self.__calculate_gps_for_mapbox_plugin(map_obj)
        # if self.with_ODM and self.placeholder_map is None:
        #     self.placeholder_map = map_obj.generate_ODM_placeholder_map(self.path_to_images)
        return map_obj.get_min_and_max_coords(), map_elements


    def save_map(self, relative_path, file_name):
        msg_str = relative_path + file_name
        path = self.path_to_images
        cv2.imwrite(path + msg_str, self.cropped_map)

        print("-Saved map under ", path + msg_str)


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
        self.middle_gps = self.middle_gps = GPS(self.corner_gps_left_bottom.altitude, self.corner_gps_left_bottom.get_latitude() +
            (self.corner_gps_right_top.get_latitude() - self.corner_gps_left_bottom.get_latitude()) / 2,
            self.corner_gps_left_bottom.get_longitude() +
            (self.corner_gps_right_top.get_longitude() - self.corner_gps_left_bottom.get_longitude()) / 2)


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
            # print("single coordinate:", str_coordinates)
            coodinate = {"coordinates_string": str_coordinates, "file_name": map_element.get_image().get_image_path().split("static/")[1]}

            new_coordinates.append(coodinate)
        # print("coordinates:", new_coordinates)
        return new_coordinates


    def generate_odm_orthophoto(self, container_port, filenames, image_size=0, ir=False):
        print("-Generating ODM orthophoto...")
        if not self.with_ODM:
            print("Error: ODM is not enabled for this dataset!")
            return

        options = {'feature-quality': 'medium', 'fast-orthophoto': True, 'auto-boundary': True, 'pc-ept': True,'cog': True}
        if ir:
            options = {'feature-quality': 'high', 'fast-orthophoto': True, 'auto-boundary': True, 'pc-ept': True,'cog': True}
        image_list = filenames.deepcopy()#self.filenames_rgb.copy() if not ir else self.filenames_ir.copy()
        for j, image in enumerate(image_list):
            image_list[j] = "static/" + image
        # print(image_list)
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
                # print(corner_gps_left_bottom, corner_gps_right_top)

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

