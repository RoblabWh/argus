#!/usr/bin/env python3


import json
import re
import os
import datetime as dt

import pyexifinfo as p

from .gps import GPS
from .xmp import XMP
from .camera_properties import CameraProperties


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
        ## save the python dict as json file for debugging as debugmetadta.json
        # with open('debugmetadata.json', 'w') as outfile:
        #     json.dump(self.python_dict, outfile, indent=4, separators=(',', ': '))

        #print(self.python_dict, flush=True)


        self.gps_coordinate = None
        self.xmp_metadata = None
        self.camera_properties = None
        self.image_size = None
        self.creation_time = None
        self.creation_time_str = None
        self.ir = False
        self.pano = False
        self.pano_data = None
        self.usable = True


        try:
            self.read_image_size()
            self.read_creation_time()
            self.read_xmp_metadata()
            self.read_xmp_projection_type()
            if not self.pano:
                self.read_camera_properties()
                self.check_ir()
            self.read_gps_coordinate()
        except Exception as e:
            print("Error reading metadata: " + str(e))
            self.usable = False




        #print(self.python_dict)

    def read_creation_time(self):
        try:
            self.creation_time_str = (str(self._get_if_exist(self.python_dict, 'EXIF:CreateDate')))
            print("creation_time_str: '" + self.creation_time_str + "' (from EXIF:CreateDate)")
            # use dt to convert to timestamp
            self.creation_time = dt.datetime.strptime(self.creation_time_str, '%Y:%m:%d %H:%M:%S').timestamp()
            #creation_time = self.creation_time_str.replace(':', '')
            #creation_time = creation_time.replace(' ', '')
            #self.creation_time = int(creation_time) % 1000000
            # print("creation_time_str: '" + self.creation_time_str + "' (from EXIF:CreateDate)" + " creation_time: " + str(self.creation_time) + "time wo modulo" + str(int(creation_time)))
        except:
            #trying to read the creation time from the file itself
            self.creation_time = os.path.getmtime(self.image_path)
            self.creation_time_str = dt.datetime.fromtimestamp(self.creation_time).strftime('%Y:%m:%d %H:%M:%S')




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

        if self.pano:
            self.pano_data['coordinates'] = [
                self.gps_coordinate.get_latitude(),
                self.gps_coordinate.get_longitude()
            ]

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

    def check_ir(self):
        """
        Checking if the image is an IR image
        :return:
        """

        if self.read_xmp_ir():
            self.enable_ir()
            return

        if self.check_for_camera_model_ir_image_size():
            self.enable_ir()
            return

        if self.check_filename_ir():
            self.enable_ir()
            return



    def read_xmp_ir(self):
        """
        Trying to read IR metadata, if available
        :return:
        """

        try:
            imageSource = self._get_if_exist(self.python_dict, 'XMP:ImageSource')
            if "infrared" in imageSource or "Infrared" in imageSource or "InfraRed" in imageSource or "InfraredCamera" in imageSource:
                print("IR image detected by XMP:ImageSource" + imageSource, flush=True)
                return True
        except:
            return False

    def check_for_camera_model_ir_image_size(self):
        """
        Checking if the image has specific dimensions known to be uses for IR images of guven camera model
        :return: True if the image is an IR image
        """
        camera_model_name = self.camera_properties.get_model()
        #print("trying to check the image size of camera_model_name: " + str(camera_model_name) + " to check for ir", flush=True)
        with open('./mapping/ir_camera_resolutions.json') as f:
            data = json.load(f)
            if camera_model_name in data:
                size = data[camera_model_name]
                x_ref = size["x"]
                y_ref = size["y"]
                # print("image size from ir_camera_resolutions.json: x" + str(x_ref) + " y" + str(y_ref), flush=True)
                # print("image size from image: x" + str(self.image_size[0]) + " y" + str(self.image_size[1]), flush=True)
                if self.image_size[0] == x_ref and self.image_size[1] == y_ref:
                    f.close()
                    return True
                f.close()
            else:
                print("Untested configuration for camera model:\"" + str(
                    camera_model_name) + "\", please add IR image size to ir_camera_resolutions.json!")
                f.close()

        return False

    def check_filename_ir(self):
        """
        Checking if the image has knowns naming conventions for IR images
        :return: True if the image is an IR image
        """
        filename = self.image_path.split('/')[-1]
        if "IR" in filename or "ir" in filename:
            return True

        if filename.split('.')[0][-2:] == "_T":
            return True

        return False


    def read_xmp_projection_type(self, key='XMP:ProjectionType'):

        try:
            # print(self.python_dict)
            projectionType = self._get_if_exist(self.python_dict, key)
            # print("projectionType: " + projectionType)
            if projectionType == "pano":
                projectionType = "equirectangular"

            if projectionType != "equirectangular":
                return

            self.pano = True

            short_path = self.image_path[self.image_path.find("projects"):]
            print("---PANO--- short_path: " + short_path, flush=True)
            # print("short_path: " + short_path, flush=True)
            author = "WHS-Team DRZ"
            title = "Pano taken at" + str(self.creation_time)

            coordinates = None
            if self.gps_coordinate is not None:
                coordinates = [
                    self.gps_coordinate.get_latitude(),
                    self.gps_coordinate.get_longitude()
                ]

            self.pano_data = dict(file=short_path, author=author, title=title, type=projectionType, coordinates=coordinates)
            # print(self.pano_data, flush=True)
        except:
            if key == 'XMP:ProjectionType':
                self.read_xmp_projection_type(key='EXIF:XPKeywords')
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
        model = self.camera_properties.model + "_IR"
        fl = None
        fov = None
        try:
            fl = self.get_data_from_camera_specs(model, 'EXIF:FocalLength')
            fov = self.get_data_from_camera_specs(model, 'Composite:FOV')
        except:
            #print(f"no specific ir camera properties found in camera_specs.json for model: { self.camera_properties.get_model }")
            return

        self.camera_properties.fl = fl
        self.camera_properties.fov = fov

    def get_data_from_camera_specs(self,camera_model_name, key):
        with open('./mapping/camera_specs.json') as f:
                data = json.load(f)
                if camera_model_name in data:
                    val = float(data[camera_model_name][key])
                    msg = "Using camera_specs.json..."
                    # print(msg, end='\r', flush=True)
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

    def update_path(self, path):
        self.image_path = path
        if self.pano:
            print("---PANO--- updating path: " + path, flush=True)
            self.pano_data['file'] = path
