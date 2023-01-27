#!/usr/bin/env python3
__author__      = "Artur Leinweber, Max Schulte"
__copyright__ = "Copyright 2020"
__license__ = "GPL"
__maintainer__ = "Max Schulte"
__email__ = "arturleinweber@live.de"
__status__ = "Production"

import json

import cv2
import os
import shutil 
import datetime
import webbrowser
import multiprocessing
import time
import sys
from weather import Weather
from datetime import datetime, time

from path_reader import PathReader
from image import Image
from map_scaler import MapScaler
from map import Map
from feature_matcher import FeatureMatcher
from html_map import HTMLMap
from pano_filter import PanoFilter
from gimbal_pitch_filter import GimbalPitchFilter
from infrared_rgb_sorter import InfraredRGBSorter
from OdmTaskManager import OdmTaskManager

class ImageMapper:
    def __init__(self, path_to_images, map_width_px, map_height_px, blending, optimize, max_gimbal_pitch_deviation, with_ODM):
        if path_to_images[-1] != "/":
            path_to_images += "/"
        self.path_to_images = path_to_images
        self.map_width_px = map_width_px 
        self.map_height_px = map_height_px
        self.blending = blending
        self.map_elements = None
        self.final_map = None
        self.optimize = optimize
        self.max_gimbal_pitch_deviation = max_gimbal_pitch_deviation
        self.with_ODM = with_ODM
        self.html_file_name = None
        self.corner_gps_right_top = None
        self.corner_gps_left_bottom = None
        self.middle_gps = None
        self.CONTAINED_DJI_INFRARED_IMAGES = False
        self.placeholder_map = None

   
    @staticmethod
    def generate_images(image_paths):
        images = list()
        for path in image_paths:
            #print(path)
            images.append(Image(path))
        return images
        
    def create_flight_report(self, pano_files):
        before_filter_time = datetime.datetime.now().replace(microsecond=0)
          
        self.map_scaler = None
        image_paths = list()
        images = list()
        image_paths = PathReader.read_path(self.path_to_images,("DJI") ,(".JPG",".jpg"), sort=False)

        print("-Loading " + str(len(image_paths)) + " images...")
        pool = multiprocessing.Pool(6)
        images = pool.map(ImageMapper.generate_images, [image_paths])[0]

        print("-Sorting " + str(len(images)) +  " images by creation time...")
        images.sort(key=lambda x: x.get_exif_header().get_creation_time())

        if len(images) < 4 :
            print("-Number of loaded image paths: ", len(images))
            exit()
        
        filtered_images = GimbalPitchFilter(89-self.max_gimbal_pitch_deviation).filter(images)
        filtered_images = PanoFilter("pano").filter(filtered_images)
        print("-Number of used images after filtering:", len(filtered_images))
        after_filter_time = datetime.datetime.now().replace(microsecond=0)
        filter_time = after_filter_time - before_filter_time
        start_time = datetime.datetime.now().replace(microsecond=0)
        self.__check_for_dji_infrared_images(filtered_images)
        
        if self.CONTAINED_DJI_INFRARED_IMAGES:
            (infrared_images, rgb_images) = InfraredRGBSorter().sort(filtered_images)
            self.__move_images_to_folder("ir/", infrared_images)
            self.__calculate_map(infrared_images)
            self.map_elements_ir = self.map_elements.copy()
            infrared_map_file_name = self.__create_file_name_string()
            self.save_map("ir/", infrared_map_file_name)
            middle_time = datetime.datetime.now().replace(microsecond=0)
            self.__create_html("ir/", infrared_map_file_name, str(middle_time-start_time+filter_time/2), pano_files, is_ir = True)
            
            self.__calculate_map(rgb_images)
            rgb_map_file_name = self.__create_file_name_string()
            self.save_map("", rgb_map_file_name)
            end_time = datetime.datetime.now().replace(microsecond=0)
            self.__create_html("",rgb_map_file_name, 
                               str(end_time-middle_time+filter_time/2),
                               pano_files,
                               "ir/", 
                               "flight_report_" + str(infrared_map_file_name.split(".")[0])+".html", 
                               infrared_map_file_name)
            
        else:
            self.__calculate_map(filtered_images)
            map_file_name = self.__create_file_name_string()
            self.save_map("", map_file_name)
            end_time = datetime.datetime.now().replace(microsecond=0)
            self.__create_html("",map_file_name, end_time-start_time+filter_time, pano_files)

    def __calculate_map(self, filtered_images):        
        self.map_scaler = MapScaler(filtered_images, self.map_width_px, self.map_height_px)
        self.map_elements = self.map_scaler.get_map_elements()
        map_offset = self.map_scaler.get_map_offset()
        #print(map_offset, "map offset")
        #self.__optimize_map_DEPRECATED()
            
        map_obj = Map(self.map_elements,
                      self.map_width_px  + map_offset,
                      self.map_height_px + map_offset,
                      self.blending, 
                      self.map_scaler.get_scale_px_per_m(),
                      self.optimize)
                      
        print("-Creating map...             ")
        self.final_map = map_obj.create_map()
        self.cropped_map = map_obj.get_cropped_map()
        self.__calculate_gps_for_mapbox_plugin(map_obj)
        if self.with_ODM and self.placeholder_map is None:
            self.placeholder_map = map_obj.generate_ODM_placeholder_map(self.path_to_images)
    
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
            if(width_0 != width_1 and height_0 != height_1):
                self.CONTAINED_DJI_INFRARED_IMAGES = True
                print("-Dataset contains infrared images...")
                return
        print("-Dataset does not contain infrared images...")



    def __calculate_gps_for_mapbox_plugin(self, map_obj):
        origin_gps = self.map_elements[0].get_image().get_exif_header().get_gps()
        origin_location = self.map_elements[0].get_rotated_rectangle().get_center()
        min_x, max_x, min_y, max_y = map_obj.get_min_and_max_coords()
        corner_location_right_top = (max_x, max_y)
        corner_location_left_bottom = (0, 0)       
        self.corner_gps_right_top = self.map_scaler.calculate_corner_gps_coordinates(origin_gps, 
                                                                                     origin_location, 
                                                                                     corner_location_right_top)
        
        self.corner_gps_left_bottom = self.map_scaler.calculate_corner_gps_coordinates(origin_gps,
                                                                                       origin_location, 
                                                                                       corner_location_left_bottom)
        self.middle_gps = self.map_scaler.get_middle_gps()
            
    def __move_images_to_folder(self, folder, images):
        mv_path = self.path_to_images + folder
        print("-Moving " + str(len(images)) + " infrared images to " + mv_path)
        if not os.path.exists(mv_path):
            os.mkdir(mv_path)
            
        for image in images:
            img_path = image.get_image_path()
            img_name = img_path.split("/")[-1]
            new_image_path = mv_path + img_name
            shutil.move(img_path, new_image_path)
            image.update_path(new_image_path)

    def __optimize_map_DEPRECATED(self):
        angle_range = 5
        optimization_rounds_per_map_element = 1
        inaccuracy_m = 5
        spreading_range = int(self.map_scaler.get_scale_px_per_m() * inaccuracy_m)
        quantity = 10

        if self.optimize:
            print("Starting optimization...")

            print("- inaccuracy angle: ", angle_range,"[°]")
            #print("- inaccuracy of GPS: ", inaccuracy_m," [m]")
            #print("- quantity of spreading: ", quantity)
            #print("- spreading range: ", spreading_range," [px]")
            #randomizer = Randomizer(self.map_elements, spreading_range, quantity, (Randomizer.get_normal), (Comparator.get_ssim))
            features = FeatureMatcher(self.map_elements, spreading_range, angle_range, optimization_rounds_per_map_element)
            self.map_elements = features.optimize()

    def get_map(self):
        return self.final_map
 
    def __create_file_name_string(self):
        time_and_date =  str((datetime.datetime.now().replace(microsecond=0))).replace(":","_").replace(" ","_")
        file_name = ("map_" +
                  str(self.map_width_px) +
                  "x" +
                  str(self.map_height_px) +
                  "_" +
                  time_and_date +
                  "_optimize_" +
                  str(self.optimize) +
                  ".png")
                  
        return file_name
 
    def get_cropped_map(self):
        return self.cropped_map

    def save_map(self, relative_path, file_name):
        msg_str = relative_path + file_name
                  
        path = self.path_to_images

        cv2.imwrite(path + msg_str,self.cropped_map)
        if self.with_ODM:
            cv2.imwrite(path+relative_path+"placeholder_map.png", self.placeholder_map)

        print("-Saved map under ", path + msg_str)
    
    def __create_html(self, folder, file_name, processing_time, pano_files, ir_path=None, ir_html_file_name=None, ir_map_name=None, is_ir=False ):
        path = self.path_to_images
        # if self.path_to_images[-1] != "/":
        #     path += "/"

        self.html_file_name = "flight_report_" + str(file_name.split(".")[0])
        self.report_path = path + folder + self.html_file_name if folder != None else path + self.html_file_name

        html_map = HTMLMap(self.map_elements,
                           self.cropped_map.shape[0],
                           self.cropped_map.shape[1],
                           self.report_path,
                           file_name, 
                           self.map_scaler.get_area_in_m(), 
                           self.map_scaler.get_avg_altitude(),
                           processing_time,
                           self.corner_gps_left_bottom,
                           self.corner_gps_right_top,
                           self.middle_gps,
                           ir_path,
                           ir_html_file_name,
                           ir_map_name,
                           is_ir,
                           self.with_ODM,
                           pano_files)
        print("-Creating HTML file...          ")                   
        html_map.create_html_file()

    def show_flight_report(self):
        print('Trying to open HTML file...' + str(self.path_to_images) + str(self.html_file_name)+ ".html")
        # webbrowser.open(os.path.abspath(str(self.path_to_images) + str(self.html_file_name)+ ".html"))
        webbrowser.open(os.path.abspath(self.report_path+ ".html"))

    def generate_odm_orthophoto(self, container_port, image_size):
        options = [{'feature-quality': 'medium', 'fast-orthophoto': True, 'auto-boundary': True, 'pc-ept': True,'cog': True},
                   {'feature-quality': 'high', 'fast-orthophoto': True, 'auto-boundary': True, 'pc-ept': True,'cog': True}]
        image_lists = []
        image_lists.append(self.extract_image_paths_from_map_elements(self.map_elements))
        if self.CONTAINED_DJI_INFRARED_IMAGES:
            image_lists.append(self.extract_image_paths_from_map_elements(self.map_elements_ir))

        taskmanager = OdmTaskManager(self.path_to_images, container_port)

        #  run in loop over image_lists
        for i, list in enumerate(image_lists):
            if(i == 0):
                taskmanager.set_images_scaled(list, image_size)
            else:
                taskmanager.set_images(list)

            taskmanager.run_task(options[i])

            while True:
                if not taskmanager.task_running():
                    break
                time.sleep(2)

            if taskmanager.task_complete:
                with open('results/odm_georeferencing/odm_georeferenced_model.info.json', 'r') as j:
                    contents = json.loads(j.read())
                    bbox = contents['stats']['bbox']['EPSG:4326']['bbox']
                    corner_gps_left_bottom = (bbox['minx'],bbox['miny'])
                    corner_gps_right_top = (bbox['maxx'],bbox['maxy'])
                #Todo, bounds irgendwie nutzen
                print(corner_gps_left_bottom, corner_gps_right_top)

                im = cv2.imread("results/odm_orthophoto/odm_orthophoto.tif", cv2.IMREAD_UNCHANGED)
                target_path = self.path_to_images if(i == 0) else self.path_to_images + "ir/"
                cv2.imwrite(target_path+ "map_odm_orthophoto.png", im)

        taskmanager.close()


    def extract_image_paths_from_map_elements(self, map_elements):
        image_paths = []
        for map_element in map_elements:
            image_paths += [map_element.get_image().get_image_path()]
        return image_paths

    def get_date(self):
        return self.map_elements[0].get_image().get_exif_header().get_creation_time_str()

    def calculate_metadata(self):
        self.pre_process_images()
        # self.mapping_images()

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

        flight_time_str = "long"#str(flight_time).split(":")
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
            actual_weather = Weather(self.map_elements[0].get_image().get_exif_header().get_gps().get_latitude(), self.map_elements[0].get_image().get_exif_header().get_gps().get_longitude(), "e9d56399575efd5b03354fa77ef54abb")
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



        flight_data_entrys = ['Date', 'Time', 'Location', 'Area Covered', 'Flight Time', 'Processing Time', 'Images',
                              'Image Resolution', 'Avg. Flight Height']
        flight_data = []
        # for entry in flight_data_entrys:
        #     flight_data.append({"description": entry, "value": "yyy"})
        flight_data.append({"description": 'Date', "value": date})
        flight_data.append({"description": 'Time', "value": "time"})
        flight_data.append({"description": 'Location', "value": self.location})
        flight_data.append({"description": 'Area Covered', "value": "yyy"})
        flight_data.append({"description": 'Flight Time', "value": flight_time_str})
        flight_data.append({"description": 'Processing Time', "value": "yyy"})
        flight_data.append({"description": 'Images', "value": len(self.map_elements)})
        flight_data.append({"description": 'Image Resolution', "value": str(x_res) + " x " + str(y_res)})
        flight_data.append({"description": 'Avg. Flight Height', "value": "yyy"})


        camera_specification_entrys = ['Camera Model', 'Focal Length', 'Horizontal FOV', 'Vertical FOV', 'Sensor Size']
        camera_specs = []
        # for entry in camera_specification_entrys:
        #     camera_specs.append({"description": entry, "value": "aaa"})
        camera_specs.append({"description": 'Camera Model', "value": camera_model})
        camera_specs.append({"description": 'Focal Length', "value": camera_focal_length})
        camera_specs.append({"description": 'Horizontal FOV', "value": camera_fov})
        camera_specs.append({"description": 'Vertical FOV', "value": camera_vertical_fov})
        camera_specs.append({"description": 'Sensor Size', "value": str(sensor_width) + " x " + str(sensor_height)})


        weather_entrys = ['Temperature', 'Humidity', 'Air Preasure', 'Wind Speed', 'Wind Direction', 'Visibility']
        weather = []
        # for entry in weather_entrys:
        #     weather.append({"description": entry, "value": "www"})
        weather.append({"description": 'Temperature', "value": temperature})
        weather.append({"description": 'Humidity', "value": humidity})
        weather.append({"description": 'Air Preasure', "value": altimeter})
        weather.append({"description": 'Wind Speed', "value": wind_speed})
        weather.append({"description": 'Wind Direction', "value": wind_dir_degrees})
        weather.append({"description": 'Visibility', "value": visibility})

        return flight_data, camera_specs, weather

    def pre_process_images(self):
        before_filter_time = datetime.now().replace(microsecond=0)

        self.map_scaler = None
        image_paths = list()
        images = list()
        image_paths = PathReader.read_path(self.path_to_images, ("DJI"), (".JPG", ".jpg"), sort=False)

        print("-Loading " + str(len(image_paths)) + " images...")
        pool = multiprocessing.Pool(6)
        images = pool.map(ImageMapper.generate_images, [image_paths])[0]

        print("-Sorting " + str(len(images)) + " images by creation time...")
        images.sort(key=lambda x: x.get_exif_header().get_creation_time())

        if len(images) < 4:
            print("-Number of loaded image paths: ", len(images))
            exit()

        self.filtered_images = GimbalPitchFilter(89 - self.max_gimbal_pitch_deviation).filter(images)
        self.filtered_images = PanoFilter("pano").filter(self.filtered_images)
        print("-Number of used images after filtering:", len(self.filtered_images))
        after_filter_time = datetime.now().replace(microsecond=0)
        filter_time = after_filter_time - before_filter_time
        start_time = datetime.now().replace(microsecond=0)
        self.__check_for_dji_infrared_images(self.filtered_images)

        self.map_scaler = MapScaler(self.filtered_images, self.map_width_px, self.map_height_px)
        self.map_elements = self.map_scaler.get_map_elements()

    def mapping_images(self):
        if self.CONTAINED_DJI_INFRARED_IMAGES:
            (infrared_images, rgb_images) = InfraredRGBSorter().sort(self.iltered_images)
            self.__move_images_to_folder("ir/", infrared_images)
            self.__calculate_map(infrared_images)
            self.map_elements_ir = self.map_elements.copy()
            infrared_map_file_name = self.__create_file_name_string()
            self.save_map("ir/", infrared_map_file_name)
            middle_time = datetime.now().replace(microsecond=0)
            self.__create_html("ir/", infrared_map_file_name, str(middle_time - start_time + filter_time / 2),
                               pano_files, is_ir=True)

            self.__calculate_map(rgb_images)
            rgb_map_file_name = self.__create_file_name_string()
            self.save_map("", rgb_map_file_name)
            end_time = datetime.datetime.now().replace(microsecond=0)
            self.__create_html("", rgb_map_file_name,
                               str(end_time - middle_time + filter_time / 2),
                               pano_files,
                               "ir/",
                               "flight_report_" + str(infrared_map_file_name.split(".")[0]) + ".html",
                               infrared_map_file_name)

        else:
            self.__calculate_map(filtered_images)
            map_file_name = self.__create_file_name_string()
            self.save_map("", map_file_name)
            end_time = datetime.datetime.now().replace(microsecond=0)
            self.__create_html("", map_file_name, end_time - start_time + filter_time, pano_files)