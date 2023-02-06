#!/usr/bin/env python3


import json
import re

import pyexifinfo as p

from gps import GPS
from xmp import XMP
from camera_properties import CameraProperties


class ExifHeader:
    def __init__(self, image_path):
        """
        Constructor
        :param image_path: image path
        """
        self.image_path = image_path
        self.json_data = p.get_json(image_path)
        self.string = json.dumps(self.json_data, sort_keys=True, indent=4, separators=(',', ': '))
        self.python_dict = json.loads(self.string)[0]


        self.gps_coordinate = None
        self.xmp_metadata = None
        self.camera_properties = None
        self.image_size = None 
        self.creation_time = None
        self.creation_time_str = None       
        self.ir = False
        self.pano = False
        self.pano_data = None

        self.read_gps_coordinate()
        self.read_xmp_metadata()
        self.read_camera_properties()
        self.read_image_size()
        self.read_creation_time()
        self.read_xmp_ir()
        self.read_xmp_projection_type()


        #print(self.python_dict)   

    def read_creation_time(self):
        self.creation_time_str = (str(self._get_if_exist(self.python_dict, 'EXIF:CreateDate')))
        creation_time = self.creation_time_str.replace(':','')
        creation_time = creation_time.replace(' ','')
        self.creation_time = int(creation_time)%1000000

    def read_image_size(self):
        image_size = (str(self._get_if_exist(self.python_dict, 'Composite:ImageSize'))).split('x')
        width =  int(image_size[0])        
        height = int(image_size[1])
        self.image_size = (width, height)

    def read_gps_coordinate(self):
        """
        Reading the gps coordinate of the image
        :return:
        """
        latitude_gms = (re.sub('[a-zA-Z\'\"]', '', str(self._get_if_exist(self.python_dict, 'EXIF:GPSLatitude')))).split()
        longitude_gms = (re.sub('[a-zA-Z\'\"]', '', str(self._get_if_exist(self.python_dict, 'EXIF:GPSLongitude')))).split()
        if 'EXIF:GPSLatitude' in self.python_dict and 'EXIF:GPSLongitude' in self.python_dict:
            latitude = GPS.gms_to_dg(latitude_gms)
            longitude = GPS.gms_to_dg(longitude_gms)
        else:
            latitude = None
            longitude = None
            # x, y = GPS.mercator_projection(latitude, longitude)                 
        relative_height = float(self._get_if_exist(self.python_dict, 'XMP:RelativeAltitude'))
        self.gps_coordinate = GPS(relative_height, latitude, longitude)
    
    def read_xmp_metadata(self):
        """
        Reading the xmp metadata of the image
        :return:
        """
        flight_yaw_degree = float(self._get_if_exist(self.python_dict, 'XMP:FlightYawDegree'))
        gimbal_yaw_degree = float(self._get_if_exist(self.python_dict, 'XMP:GimbalYawDegree'))
        flight_pitch_degree = float(self._get_if_exist(self.python_dict, 'XMP:FlightPitchDegree'))
        gimbal_pitch_degree = float(self._get_if_exist(self.python_dict, 'XMP:GimbalPitchDegree'))
        gimbal_roll_degree = float(self._get_if_exist(self.python_dict, 'XMP:GimbalRollDegree'))
        flight_roll_degree = float(self._get_if_exist(self.python_dict, 'XMP:FlightRollDegree'))
        self.xmp_metadata = XMP(flight_yaw_degree, flight_pitch_degree, flight_roll_degree, gimbal_yaw_degree, gimbal_pitch_degree, gimbal_roll_degree)

    def read_xmp_ir(self):
        """
        Trying to read IR metadata, if available
        :return:
        """

        try:
            imageSource = self._get_if_exist(self.python_dict, 'XMP:ImageSource')
            if "infrared" in imageSource or "ir" in imageSource or "Infrared" in imageSource or "IR" in imageSource or "InfraRed" in imageSource:
                self.enable_ir()
        except:
            return

    def read_xmp_projection_type(self):
        try:
            # print(self.python_dict)
            projectionType = self._get_if_exist(self.python_dict, 'XMP:ProjectionType')
            print(projectionType)

            self.pano = True

            short_path = self.image_path[self.image_path.find("uploads"):]
            author = "WHS-Team DRZ"
            title = "Pano taken at" + str(self.creation_time)

            self.pano_data = dict(file=short_path, author=author, title=title, type=projectionType, coordinates=[
                self.gps_coordinate.get_latitude(),
                self.gps_coordinate.get_longitude()
            ])
            # print(self.pano)
        except:
            return

    def read_camera_properties(self):
        """
        Reading the camera properties of the image
        :return:
        """
        fov = None
        fl = None
        camera_model_name = str(self._get_if_exist(self.python_dict, 'EXIF:Model'))

        try:
            fl = self.get_data_from_camera_specs(camera_model_name, 'EXIF:FocalLength')
        except:
            fl = float(((self._get_if_exist(self.python_dict, 'EXIF:FocalLength').split())[0]))

        try:
            fov = self.get_data_from_camera_specs(camera_model_name,'Composite:FOV')
        except:
            fov = float(((self._get_if_exist(self.python_dict, 'Composite:FOV').split())[0]))

        #print('fov: ' + str(fov), 'fl: ' + str(fl), 'camera_model_name: ' + camera_model_name)

        self.camera_properties = CameraProperties(camera_model_name, fov, fl)


    def enable_ir(self):
        self.ir = True
        self.camera_properties.model += "_IR"
        fl = None
        fov = None
        try:
            fl = self.get_data_from_camera_specs(self.camera_properties.get_model,
                                                                        'EXIF:FocalLength')
            fov = self.get_data_from_camera_specs(self.camera_properties.get_model,
                                                                         'Composite:FOV')
        except:
            #print(f"no specific ir camera properties found in camera_specs.json for model: { self.camera_properties.get_model }")
            return

        self.camera_properties.fl = fl
        self.camera_properties.fov = fov

    def get_data_from_camera_specs(self,camera_model_name, key):
        with open('camera_specs.json') as f:
                data = json.load(f)
                if camera_model_name in data:
                    val = float(data[camera_model_name][key])
                    msg = "Using camera_specs.json..."
                    print(msg, end='\r', flush=True)
                    f.close()
                else:
                    msg = "Untested configuration for camera model:\""+str(camera_model_name)+"\", please add Horizontal FOV and Focal Length to camera_specs.json!"
                    # exit()
                    f.close()
                    raise Exception(msg)
                return val

    def get_gps(self):
        """
        Returning the gps coordinate.
        :return: gps coordinate
        """
        return self.gps_coordinate

    def get_xmp(self):
        """
        Returning the gps coordinate.
        :return: xmp metadata
        """
        return self.xmp_metadata

    def get_camera_properties(self):
        """
        Returning the camera properties.
        :return: camera properties
        """
        return self.camera_properties
    
    def get_image_size(self):
        return self.image_size

    def get_creation_time(self):
        return self.creation_time

    def get_creation_time_str(self):
        return self.creation_time_str

    def get_keyword(self):
        keywords = ""
        key = 'EXIF:XPKeywords'
        if key in self.python_dict:
            keywords =  self.python_dict[key]
        return keywords

    def _get_if_exist(self, data, key):
        """
        Getting entry data if the key exists.
        :param data: dictionary
        :param key: key
        :return: entry or 0 if the key not exist
        """
        if key in data:
            return data[key]
        else:
            msg = str(key) + " does not exist in EXIF-Header of input image: " + str(self.image_path)
            raise Exception(msg)
