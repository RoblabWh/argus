
import cv2
import multiprocessing
import time
import sys
from weather import Weather
from datetime import datetime, date, time
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

        self.map_elements = None
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

        # Generate map elements using a MapScaler object
        self.map_scaler = MapScaler(self.filtered_images, self.map_width_px, self.map_height_px)
        self.map_elements = self.map_scaler.get_map_elements()
        self.__calculate_gps_for_mapbox_plugin()
        return True


    # def preprocess_calculate_metadata(self):

    def preprocess_calculate_metadata(self):#, report_id, file_names):
        # self.current_report_id = report_id
        # if not self.pre_process_images(file_names): return None
        #

        date = str(self.map_elements[0].get_image().get_exif_header().get_creation_time_str())
        try:
            self.location = str(self.map_elements[0].get_image().get_exif_header().get_gps().get_address())
        except:
            self.location = str("N/A")
            print("-Ignoring reverse adress search....")
            print("--", sys.exc_info()[0])

        flight_time_last = self.map_elements[-1].get_image().get_exif_header().get_creation_time()
        flight_time_first = self.map_elements[0].get_image().get_exif_header().get_creation_time()
        last = time(int(flight_time_last / 10000), int(flight_time_last % 10000 / 100), int(flight_time_last % 100))
        first = time(int(flight_time_first / 10000), int(flight_time_first % 10000 / 100), int(flight_time_first % 100))
        # flight_time = datetime.combine(datetime.date.min, last) - datetime.combine(datetime.date.min, first)

        flight_time_str = "long"  # str(flight_time).split(":")
        # flight_time_str = flight_time_str[-3] + " h : " + flight_time_str[-2] + " m : " + \
        #                        flight_time_str[-1] + " s"
        x_res = self.map_elements[0].get_image().get_width()
        y_res = self.map_elements[0].get_image().get_height()

        camera_properties = self.map_elements[0].get_image().get_exif_header().get_camera_properties()
        camera_model = camera_properties.get_model()
        camera_focal_length = camera_properties.get_focal_length()
        camera_fov = camera_properties.get_fov()
        camera_vertical_fov = camera_properties.get_vertical_fov()
        sensor_width, sensor_height = camera_properties.get_sensor_size()

        # print(self.area_k, self.avg_altitude, self.date, self.location, self.flight_time_str, self.camera_model, self.camera_fov)
        try:
            actual_weather = Weather(self.map_elements[0].get_image().get_exif_header().get_gps().get_latitude(),
                                     self.map_elements[0].get_image().get_exif_header().get_gps().get_longitude(),
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
        # flight_data_entrys = ['Date', 'Time', 'Location', 'Area Covered', 'Flight Time', 'Processing Time', 'Images',
        #                       'Image Resolution', 'Avg. Flight Height']
        # for entry in flight_data_entrys:
        #     flight_data.append({"description": entry, "value": "yyy"})
        flight_data.append({"description": 'Date', "value": date})
        flight_data.append({"description": 'Time', "value": "time"})
        flight_data.append({"description": 'Location', "value": self.location})
        flight_data.append({"description": 'Area Covered', "value": self.map_scaler.get_area_in_m()})
        flight_data.append({"description": 'Flight Time', "value": flight_time_str})
        flight_data.append({"description": 'Processing Time', "value": "yyy"})
        flight_data.append({"description": 'Images', "value": len(self.map_elements)})
        flight_data.append({"description": 'Image Resolution', "value": str(x_res) + " x " + str(y_res)})
        flight_data.append({"description": 'Avg. Flight Height', "value": self.map_scaler.get_avg_altitude()})

        camera_specs = []
        #camera_specification_entrys = ['Camera Model', 'Focal Length', 'Horizontal FOV', 'Vertical FOV', 'Sensor Size']
        # for entry in camera_specification_entrys:
        #     camera_specs.append({"description": entry, "value": "aaa"})
        camera_specs.append({"description": 'Camera Model', "value": camera_model})
        camera_specs.append({"description": 'Focal Length', "value": camera_focal_length})
        camera_specs.append({"description": 'Horizontal FOV', "value": camera_fov})
        camera_specs.append({"description": 'Vertical FOV', "value": camera_vertical_fov})
        camera_specs.append({"description": 'Sensor Size', "value": str(sensor_width) + " x " + str(sensor_height)})

        weather = []
        #weather_entrys = ['Temperature', 'Humidity', 'Air Preasure', 'Wind Speed', 'Wind Direction', 'Visibility']
        # for entry in weather_entrys:
        #     weather.append({"description": entry, "value": "www"})
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

        map = {
            "center": [latc, longc],
            "zoom": 18,
            "rgbMapFile": "default/MapRGBMissing.jpeg",
            "rgbMapBounds": bounds,
            "irMapFile": "default/MapIRMissing.jpeg",
            "irMapBounds": bounds,
        }


        return flight_data, camera_specs, weather, map
    #
    # def pre_process_images(self, selection=None):
    #     # Read all image paths
    #     image_paths = list()
    #     images = list()
    #
    #     if selection is None:
    #         image_paths = PathReader.read_path(self.path_to_images, ("DJI"), (".JPG", ".jpg"), sort=False)
    #     else:
    #         image_paths = PathReader.read_selection('./static', selection, ("DJI"), (".JPG", ".jpg"), sort=False)
    #
    #     # Read all images and generate image objects using multiprocessing
    #     pool = multiprocessing.Pool(6)
    #     images = pool.map(ImageMapper.generate_images, [image_paths])[0]
    #     images.sort(key=lambda x: x.get_exif_header().get_creation_time())
    #
    #     # Check if the minimum number of images is reached
    #     if len(images) < self.minimum_number_of_images:
    #         print("-Number of loaded image paths: ", len(images))
    #         return False
    #
    #     # Filter images
    #     self.filtered_images = GimbalPitchFilter(89 - self.max_gimbal_pitch_deviation).filter(images)
    #     self.filtered_images = PanoFilter("pano").filter(self.filtered_images)
    #
    #     #check wether infrared images are present
    #     self.__check_for_dji_infrared_images(self.filtered_images)
    #
    #     # Generate map elements using a MapScaler object
    #     self.map_scaler = MapScaler(self.filtered_images, self.map_width_px, self.map_height_px)
    #     self.map_elements = self.map_scaler.get_map_elements()
    #     return True

    def map_images(self, report_id):
        if self.current_report_id != report_id:
            #self.pre_process_images()
            return None
        if self.map_elements is None:
            print("-No map elements found!")
            return None


        #TODO add progress bar
        #TODO IR Images verarbeiten
        self.__calculate_map()
        map_file_name = "map.png"
        self.save_map(str(report_id)+'/', map_file_name)
        # end_time = datetime.datetime.now().replace(microsecond=0)
        # self.__create_html("", map_file_name, end_time - start_time + filter_time, pano_files)


        lat1 = self.corner_gps_left_bottom .get_latitude()
        long1 = self.corner_gps_left_bottom.get_longitude()
        lat2 = self.corner_gps_right_top .get_latitude()
        long2 = self.corner_gps_right_top .get_longitude()
        latc = self.middle_gps.get_latitude()
        longc = self.middle_gps.get_longitude()
        bounds = [[lat1, long1],[lat2, long2]]

        map = {
            "center": [latc, longc],
            "zoom": 18,
            "rgbMapFile": "uploads/"+str(report_id)+"/map.png",
            "rgbMapBounds": bounds,
            "irMapFile": "default/MapIRMissing.jpeg",
            "irMapBounds": bounds,
        }

        return map

    def __calculate_map(self):
        map_offset = self.map_scaler.get_map_offset()
        # print(map_offset, "map offset")
        # self.__optimize_map_DEPRECATED()

        map_obj = Map(self.map_elements,
                      self.map_width_px + map_offset,
                      self.map_height_px + map_offset,
                      self.blending,
                      self.map_scaler.get_scale_px_per_m(),
                      self.optimize)

        print("-Creating map...             ")
        self.final_map = map_obj.create_map()
        self.cropped_map = map_obj.get_cropped_map()
        # self.__calculate_gps_for_mapbox_plugin(map_obj)
        if self.with_ODM and self.placeholder_map is None:
            self.placeholder_map = map_obj.generate_ODM_placeholder_map(self.path_to_images)

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

        (width_0, height_0) = filtered_images[0].get_exif_header().get_image_size()
        for image in filtered_images:
            (width_1, height_1) = image.get_exif_header().get_image_size()
            if (width_0 != width_1 and height_0 != height_1):
                self.CONTAINED_DJI_INFRARED_IMAGES = True
                print("-Dataset contains infrared images...")
                return
        print("-Dataset does not contain infrared images...")

    def __calculate_gps_for_mapbox_plugin(self):
        origin_gps = self.map_elements[0].get_image().get_exif_header().get_gps()
        origin_location = self.map_elements[0].get_rotated_rectangle().get_center()
        # min_x, max_x, min_y, max_y = map_obj.get_min_and_max_coords()
        min_x = float("inf")
        min_y = float("inf")
        max_x = float("-inf")
        max_y = float("-inf")

        for map_element in self.map_elements:
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
        self.corner_gps_right_top = self.map_scaler.calculate_corner_gps_coordinates(origin_gps,
                                                                                     origin_location,
                                                                                     corner_location_right_top)

        self.corner_gps_left_bottom = self.map_scaler.calculate_corner_gps_coordinates(origin_gps,
                                                                                       origin_location,
                                                                                       corner_location_left_bottom)
        self.middle_gps = self.map_scaler.get_middle_gps()