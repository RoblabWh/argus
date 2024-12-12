import json
import re
import os
import datetime as dt

import pyexifinfo as p

from .gps import GPS
from .xmp import XMP
from .camera_properties import CameraProperties


class Metadata:

    def __init__(self, image_path, camera_metadata_tags_path="./mapping/camera_metadata_tags.json"):
        """
        Constructor
        :param image_path: image path
        """
        self.image_path = image_path
        self.data = p.get_json(image_path)
        data_string = json.dumps(self.data, sort_keys=True, indent=4, separators=(',', ': '))
        self.data_dict = json.loads(data_string)[0]

        metadata_tags = json.load(open(camera_metadata_tags_path))
        metadata_tags_dict = None

        self.usable = True
        self.ir = False
        self.pano = False
        self.pano_data = None

        self.creation_time = None
        self.creation_time_str = None
        self.image_size = None
        self.xmp_metadata = None
        self.gps_coordinate = None
        self.camera_properties = None

        self.camera_model = self.get_camera_model()

        if self.camera_model:
            try:
                metadata_tags_dict = metadata_tags[self.camera_model]
            except:
                metadata_tags_dict = None
        else:
            self.camera_model = "Unknown"

        if not metadata_tags_dict:
            metadata_tags_dict = metadata_tags['default']

        # print("Camera model: " + self.camera_model, flush=True)
        # print("Metadata tags: " + str(metadata_tags_dict), flush=True)

        self.load_metadata(metadata_tags_dict)



    def get_camera_model(self):
        """
        Return the camera model of the image
        :return: string
        """
        try:
            camera_model = self.data_dict['EXIF:Model']
        except KeyError:
            camera_model = None
        return camera_model


    def load_metadata(self, tags_dict):
        """
        Load the metadata with the given tags
        :param tags_dict: dictionary
        """
        # Load basic information that every image has like image size, date, etc.
        self.creation_time, self.creation_time_str = self.load_timestamp(tags_dict['creation_time'])
        self.image_size = self.load_image_size(tags_dict['image_size'])
        self.gps_coordinate = self.load_gps(tags_dict['gps'])

        # check if it is a panorama image
        self.pano = self.check_pano(tags_dict['projection_type'])
        if self.pano:
            return

        # check if it is an ir image
        self.ir = self.check_ir(tags_dict['ir'])

        self.camera_properties = self.load_camera_properties(tags_dict['camera_properties'], self.ir)
        self.xmp_metadata = self.load_orientation(tags_dict['orientation'])


    def load_timestamp(self, key):
        """
        Load the date from the metadata
        :param key: string
        :return: datetime
        """
        try:
            creation_time_str = (str(self._get_if_exist(self.data_dict, key)))
            creation_time = dt.datetime.strptime(creation_time_str, '%Y:%m:%d %H:%M:%S').timestamp()

        except Exception as e:
            creation_time = os.path.getmtime(self.image_path)
            creation_time_str = dt.datetime.fromtimestamp(creation_time).strftime('%Y:%m:%d %H:%M:%S')

        return creation_time, creation_time_str


    def load_image_size(self, key):
        """
        Load the image size from the metadata
        :param key: string
        :return: tuple
        """
        try:
            image_size = str(self._get_if_exist(self.data_dict, key)).split('x')
            width = int(image_size[0])
            height = int(image_size[1])
            image_size = (width, height)
        except KeyError:
            print("__UNUSABLE__ Error while loading image size", flush=True)
            image_size = None
            self.usable = False
        return image_size


    def check_pano(self, key):
        """
        Check if the image is a panorama image
        :param key: string
        :return: boolean
        """
        try:
            projection_type = self._get_if_exist(self.data_dict, key)
            if projection_type == "pano":
                projection_type = "equirectangular"

            # print("Projection type: " + projection_type, flush=True)

            if projection_type != "equirectangular":
                return False


            short_path = "./static/" + self.image_path[self.image_path.find("projects"):]
            author = "ARGUS"
            title = "Pano taken at" + str(self.creation_time)

            coordinates = None
            if self.gps_coordinate is not None:
                coordinates = [
                    self.gps_coordinate.get_latitude(),
                    self.gps_coordinate.get_longitude()
                ]

            self.pano_data = dict(file=short_path, author=author, title=title, type=projection_type,
                                  coordinates=coordinates)
            return True
        except Exception as e:
            if key == 'XMP:ProjectionType':
                return self.check_pano(key='EXIF:XPKeywords')
            return False


    def load_gps(self, keys):
        """
        Reading the gps coordinate of the image
        :param keys: dictionary
        :return: GPS object
        """
        relative_altitude = 1
        try:
            rel_alt = self._get_if_exist(self.data_dict, keys['relative_altitude'])
            #chack if there is any text like m or ft in the string
            if any(char.isdigit() for char in rel_alt):
                relative_altitude = float(re.sub('[a-zA-Z\'\"]', '', rel_alt))
            else:
                relative_altitude = float()
        except Exception as e:
            print('___UNUSABLE___ Error while loading relative altitude:' + str(e), flush=True)
            relative_altitude = 1
            self.usable = False
        try:
            latitude_gms = (
                re.sub('[a-zA-Z\'\"]', '', str(self._get_if_exist(self.data_dict, keys['latitude'])))).split()
            longitude_gms = (
                re.sub('[a-zA-Z\'\"]', '', str(self._get_if_exist(self.data_dict, keys['longitude'])))).split()
            west = False
            south = False
            if self._get_if_exist(self.data_dict, keys['latitude'])[-1] == 'S':
                south = True
            if self._get_if_exist(self.data_dict, keys['longitude'])[-1] == 'W':
                west = True
            latitude = GPS.gms_to_dg(latitude_gms, south)
            longitude = GPS.gms_to_dg(longitude_gms, west)
            return GPS(relative_altitude, latitude, longitude)
        except:
            print('___UNUSABLE___ Error while loading GPS', flush=True)
            self.usable = False
            return None


    def check_ir(self, keys):
        """
        Check if the image is an infrared image
        :param keys: dictionary
        :return: boolean
        """
        try:
            if keys['ir'] != "":
                ir_indicator = self._get_if_exist(self.data_dict, keys['ir'])
                if ir_indicator == keys['ir_value']:
                    # print("file: " + self.image_path + " is an IR image")
                    return True
                else:
                    return False
            elif keys['ir_image_size'] != "":
                ir_image_size = keys['ir_image_size']
                if self.image_size[0] == ir_image_size['x'] and self.image_size[1] == ir_image_size['y']:
                    return True
                else:
                    return False
            elif keys ['filename_suffix'] != "":
                filename_suffix = keys['filename_suffix']
                if self.image_path.endswith(filename_suffix):
                    return True
                else:
                    return False
            else:
                return False
        except:
            return False


    def load_camera_properties(self, keys, ir):
        """
        load the camera properties
        :param keys:
        :param ir:
        :return:
        """


        camera_model_name = self.camera_model + "_IR" if ir else self.camera_model
        try:
            focal_length = self.get_data_from_camera_specs(camera_model_name, keys['focal_length'])
            fov = self.get_data_from_camera_specs(camera_model_name, keys['fov'])
            camera_properties = CameraProperties(camera_model_name, fov, focal_length)
            return camera_properties
        except Exception as e:
            try:
                focal_length_str = self._get_if_exist(self.data_dict, keys['focal_length'])
                fov_str = self._get_if_exist(self.data_dict, keys['fov'])

                #seperating the unit from the value
                focal_length = float(focal_length_str.split()[0])
                fov = float(fov_str.split()[0])
                camera_properties = CameraProperties(camera_model_name, fov, focal_length)
                return camera_properties

            except Exception as e:
                print('__UNUSABLE__ Error while loading camera properties of ' + camera_model_name + ': ' + str(e), flush=True)
                self.usable = False
                return None





    def load_orientation(self, keys):
        """
        Load the orientation of the uav
        :param keys:
        :return: XMP object
        """
        try:
            flight_yaw_degree = float(self._get_if_exist(self.data_dict, keys['flight_yaw']))
            gimbal_yaw_degree = float(self._get_if_exist(self.data_dict, keys['gimbal_yaw']))
            flight_pitch_degree = float(self._get_if_exist(self.data_dict, keys['flight_pitch']))
            gimbal_pitch_degree = float(self._get_if_exist(self.data_dict, keys['gimbal_pitch']))
            gimbal_roll_degree = float(self._get_if_exist(self.data_dict, keys['gimbal_roll']))
            flight_roll_degree = float(self._get_if_exist(self.data_dict, keys['flight_roll']))
            xmp_metadata = XMP(flight_yaw_degree, flight_pitch_degree, flight_roll_degree, gimbal_yaw_degree,
                                    gimbal_pitch_degree, gimbal_roll_degree)
            return xmp_metadata
        except Exception as e:
            print("__UNUSABLE__ Error while loading orientation: " + str(e), flush=True)
            self.usable = False
            return None

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


    def get_data_from_camera_specs(self,camera_model_name, key):
        with open('./mapping/camera_specs.json') as f:
                data = json.load(f)
                # print("Camera model name: " + camera_model_name, flush=True)
                # print("Key: " + key, flush=True)
                # print("Data: " + str(data), flush=True)
                if camera_model_name in data:
                    val = float(data[camera_model_name][key])
                    # print("Value: " + str(val) + " for key: " + key + " with model: " + camera_model_name, flush=True)
                    msg = "Using camera_specs.json..."
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
        if key in self.data_dict:
            keywords = self.data_dict[key]
        return keywords

    def update_path(self, path):
        self.image_path = path
        if self.pano:
            print("---PANO--- updating path: " + path, flush=True)
            self.pano_data['file'] = path