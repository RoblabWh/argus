import multiprocessing
import os
import shutil
import sys

from .image import Image
from .infrared_rgb_sorter import InfraredRGBSorter
from .weather import Weather
import datetime as dt

class ImageProcessor:
    def __init__(self, image_paths, rgb_images, ir_images, pano_images):
        self.all_image_paths = []
        self.all_images = []
        self.all_image_paths = image_paths
        self.all_rgb_images = rgb_images
        self.all_ir_images = ir_images
        self.all_pano_images = pano_images
        self.all_sorted_images = []
        self.all_panos = []

        self.couples_path_list = []

    @staticmethod
    def generate_images(image_paths):
        images = list()
        for path in image_paths:
            # print(path)
            try:
                images.append(Image(path))
            except:
                print("Error while processing image: ", path)
                print(sys.exc_info())
        return images


    def _chunks(self, lst, n):
        """Yield successive n-sized chunks from lst."""
        for i in range(0, len(lst), n):
            yield lst[i:i + n]
    def generate_images_from_paths(self):

        for image in self.all_rgb_images:
            path = image.get_image_path()
            self.all_image_paths.remove(path)

        for image in self.all_ir_images:
            path = image.get_image_path()
            self.all_image_paths.remove(path)

        print('all image paths: ', self.all_image_paths, flush=True)
        print('pano length: ', len(self.all_pano_images), flush=True)
        for image in self.all_pano_images:
            path = image.get_image_path()
            print('pano path: ', path, flush=True)
            self.all_image_paths.remove(path)


        nmbr_of_processes = len(os.sched_getaffinity(0)) #6
        #print('number of processes: ', nmbr_of_processes)
        if nmbr_of_processes < len(self.all_image_paths):
            nmbr_of_processes = len(self.all_image_paths)
        image_paths_list = list(self._chunks(self.all_image_paths, int(len(self.all_image_paths) / nmbr_of_processes) + 1))
        pool = multiprocessing.Pool(nmbr_of_processes)
        images_lists = pool.map(ImageProcessor.generate_images, image_paths_list)

        images = []
        for lst in images_lists:
            images += (lst)

        self.all_images = images

    def filter_images(self):
        for image in self.all_images:
            if image.get_exif_header().ir:
                self.all_ir_images.append(image)
            elif image.get_exif_header().pano:
                self.all_pano_images.append(image)
            else:
                self.all_rgb_images.append(image)


    def sort_images(self):
        self.all_rgb_images.sort(key=lambda x: x.get_exif_header().get_creation_time())
        self.all_ir_images.sort(key=lambda x: x.get_exif_header().get_creation_time())
        self.all_pano_images.sort(key=lambda x: x.get_exif_header().get_creation_time())

        self.all_images = self.all_rgb_images + self.all_ir_images + self.all_pano_images
        self.all_images.sort(key=lambda x: x.get_exif_header().get_creation_time())

    def filter_panos(self):
        self.all_panos = []

        self.all_panos = [image for image in self.all_images if image.get_exif_header().pano]
        for pano in self.all_panos:
            self.all_images.remove(pano)
            self.move_image_to_subfolder(pano, 'panos')
            #pano.generate_thumbnail()



    def get_panos(self):
        panos = []
        for pano in self.all_pano_images:
            panos.append(pano.get_exif_header().pano_data)
        return panos


    def extract_flight_data(self, flight_data=[]):
        #extract date, flight duration, location, number of total images, number of panos, average flight height, covered area
        firstImage = self.all_images[0]
        lastImage = self.all_images[-1]

        imageWithGPSData = None

        for i in range(len(self.all_images)):
            imageWithGPSData = self.all_images[i]
            if imageWithGPSData.get_exif_header().get_gps() is not None:
                break

        date = str(firstImage.get_exif_header().get_creation_time_str())
        #date is in format yyyy:mm:dd hh:mm:ss but should be changed to dd.mm.yyyy hh:mm
        date = date[8:10] + '.' + date[5:7] + '.' + date[0:4] + ' ' + date[11:16]
        time_difference_seconds = abs(lastImage.get_exif_header().get_creation_time() - firstImage.get_exif_header().get_creation_time())

        # Convert the difference to a timedelta object
        time_difference = dt.timedelta(seconds=time_difference_seconds)

        # Extract hours, minutes, and seconds from the timedelta object
        hours, remainder = divmod(time_difference.seconds, 3600)
        minutes, seconds = divmod(remainder, 60)

        # Format the difference as hh:mm:ss
        flight_duration = f'{hours:02}:{minutes:02}:{seconds:02}'

        try:
            location = str(imageWithGPSData.get_exif_header().get_gps().get_address())
        except:
            location = str("N/A")

        number_of_images = str(len(self.all_images))
        number_of_panos = str(len(self.all_panos))
        average_altitude = self._calculate_average_flight_height(self.all_images)
        covered_area = self._calculate_covered_area(self.all_images)

        if len(flight_data) != 0:
            for line in flight_data:
                if line["description"] == 'Panoramas':
                    number_of_panos = str(len(self.all_panos) + int(line["value"]))

        flight_data = []
        flight_data.append({"description": 'Date', "value": date})
        flight_data.append({"description": 'Location', "value": location})
        flight_data.append({"description": 'Area Covered', "value": covered_area})
        flight_data.append({"description": 'Avg. Altitude', "value": average_altitude})
        flight_data.append({"description": 'Flight duration', "value": flight_duration})
        flight_data.append({"description": 'Images', "value": number_of_images})
        flight_data.append({"description": 'Panoramas', "value": number_of_panos})

        return flight_data

    def _calculate_average_flight_height(self, images):
        total_altitude = 0
        for image in images:
            try:
                total_altitude += image.get_exif_header().get_gps().get_altitude()
            except:
                print("no altitude data on image: ", image.get_image_path())
        return str(round(total_altitude / len(images), 2))

    def _calculate_covered_area(self, images):
        #TODO
        return str("N/A")

    def extract_camera_specs(self):
        imageWithCameraData = None

        for i in range(len(self.all_images)):
            imageWithCameraData = self.all_images[i]
            if imageWithCameraData.get_exif_header().get_camera_properties() is not None:
                break

        if imageWithCameraData.get_exif_header().get_camera_properties() is None:
            try:
                for i in range(len(self.all_images)):
                    image = self.all_images[i]
                    if image.get_exif_header().camera_model is not None:
                        camera_specs = [{"description": 'Camera Model', "value": image.get_exif_header().camera_model},
                                        {"description": 'Focal Length', "value": "N/A"},
                                        {"description": 'Horizontal FOV', "value": "N/A"},
                                        {"description": 'Vertical FOV', "value": "N/A"},
                                        {"description": 'Sensor Size', "value": "N/A"}]

                        return camera_specs
            except Exception as e:
                print("Error while extracting camera specs: ", e)
                return [{"description": 'Camera Model', "value": "data not available"},]

        # extract camera model, focal length, horizontal_fov, vertical_fov, sensor size
        camera_properties = imageWithCameraData.get_exif_header().get_camera_properties()
        camera_model = camera_properties.get_model()
        camera_focal_length = camera_properties.get_focal_length()
        camera_fov = camera_properties.get_fov()
        camera_vertical_fov = camera_properties.get_vertical_fov()
        sensor_width, sensor_height = camera_properties.get_sensor_size()

        camera_specs = []
        camera_specs.append({"description": 'Camera Model', "value": camera_model})
        camera_specs.append({"description": 'Focal Length', "value": camera_focal_length})
        camera_specs.append({"description": 'Horizontal FOV', "value": camera_fov})
        camera_specs.append({"description": 'Vertical FOV', "value": camera_vertical_fov})
        camera_specs.append({"description": 'Sensor Size', "value": str(sensor_width) + " x " + str(sensor_height)})

        return camera_specs


    def load_weather_data(self):
        imageWithGPSData = None

        for i in range(len(self.all_images)):
            imageWithGPSData = self.all_images[i]
            if imageWithGPSData.get_exif_header().get_gps() is not None:
                break

        temperature = "N/A"
        humidity = "N/A"
        altimeter = "N/A"
        wind_speed_ms = "N/A"
        wind_speed_kmh = "?"
        wind_speed_knots = "?"
        wind_dir_degrees = "N/A"
        visibility = "N/A"
        wind_dir_cardinal = "?"
        ts = self.all_images[0].get_exif_header().get_creation_time_str()#yyyy:mm:dd hh:mm:ss
        # systems time zone
        current_time_zone = dt.datetime.now().astimezone().tzinfo
        # convert from current time zone to UTC
        ts = dt.datetime.strptime(ts, "%Y:%m:%d %H:%M:%S").replace(tzinfo=current_time_zone).astimezone(dt.timezone.utc).timestamp()
        # if ts has a decimal, it is removed
        ts = int(ts)
        try:
            default = "b13f7582ca21d76ef5ea7df897dd8a6"
            actual_weather = Weather(imageWithGPSData.get_exif_header().get_gps().get_latitude(),
                                     imageWithGPSData.get_exif_header().get_gps().get_longitude(),
                                     ts, default, api_key=None)
            # print(weather_info_lst)
            temperature = actual_weather.get_temperature()
            humidity = actual_weather.get_humidity()
            altimeter = actual_weather.get_altimeter()
            wind_speed_ms = actual_weather.get_wind_speed()
            wind_speed_kmh = actual_weather.get_wind_speed_kmh()
            wind_speed_knots = actual_weather.get_wind_speed_knots()
            visibility = actual_weather.get_visibility()
            wind_dir_degrees = actual_weather.get_wind_dir_degrees()
            wind_dir_cardinal = actual_weather.get_wind_dir_cardinal()
        except:
            print("-Ignoring weather details...")
            print("--", sys.exc_info())
            pass

        weather_data = []
        weather_data.append({"description": 'Temperature', "value": str(temperature) + "°C"})
        weather_data.append({"description": 'Humidity', "value": str(humidity) + "%"})
        weather_data.append({"description": 'Air Preasure', "value": str(altimeter) + "hPa"})
        weather_data.append({"description": 'Wind Speed', "value": str(wind_speed_ms) + "m/s" + " (" + str(wind_speed_kmh) + "km/h, " + str(wind_speed_knots) + "knots)"})
        weather_data.append({"description": 'Wind Direction', "value": str(wind_dir_degrees) + "°  (" + str(wind_dir_cardinal) + ")"})
        weather_data.append({"description": 'Visibility', "value": str(visibility) + "m"})

        return weather_data





    def generate_flight_trajectory(self):
        coordinates = []
        for image in self.all_rgb_images:
            try:
                coordinate = [image.get_exif_header().get_gps().get_latitude(),
                                image.get_exif_header().get_gps().get_longitude()]
                # if a coordinates is closer than 0.0001, to its previous one, it is not added to the list
                if len(coordinates) == 0:
                    coordinates.append(coordinate)
                elif (abs(coordinates[-1][0] - coordinate[0]) > 0.00001 and
                      abs(coordinates[-1][1] - coordinate[1]) > 0.00001):
                    coordinates.append(coordinate)
            except:
                print("no gps data on image: ", image.get_image_path())

        self.flight_trajectory = coordinates


    def move_image_to_subfolder(self, image, subfolder):
        subfolder_path = os.path.join(os.path.dirname(image.get_image_path()), subfolder)
        image_path = os.path.join(subfolder_path, os.path.basename(image.get_image_path()))
        if not os.path.exists(subfolder_path):
            os.makedirs(subfolder_path)
        shutil.move(image.get_image_path(), image_path)
        image.update_path(image_path)

    def move_images_to_subfolder(self, images, subfolder):
        for image in images:
            last_folder = os.path.basename(os.path.dirname(image.get_image_path()))
            #print(last_folder)
            if last_folder != subfolder:
                self.move_image_to_subfolder(image, subfolder)

    def generate_thumbnais(self):
        for image in self.all_rgb_images:
            image.generate_thumbnail()

        for image in self.all_panos:
            image.generate_thumbnail()

        for image in self.all_ir_images:
            image.generate_thumbnail()

    def find_couples(self):
        """
        This function finds the corresponding infrared and rgb images taken within the same second
         if no image is found, the image is added with an empty counterpart string (placeholder image)
        :return:
        """

        couples = []
        j = 0
        i = 0

        while True:
            rgb_image = None
            if i < len(self.all_rgb_images):
                rgb_image = self.all_rgb_images[i]

            while j < len(self.all_ir_images):
                ir_image = self.all_ir_images[j]

                if rgb_image is None:
                    couples.append(("", ir_image.image_path))
                    j += 1
                    continue

                if abs(rgb_image.get_exif_header().get_creation_time() - ir_image.get_exif_header().get_creation_time()) <= 1:
                    rgb_image.set_rgb_counterpart_path(ir_image.get_image_path())
                    couples.append((rgb_image.image_path, ir_image.image_path))
                    j += 1
                    break

                if rgb_image.get_exif_header().get_creation_time() < ir_image.get_exif_header().get_creation_time():
                    couples.append((rgb_image.image_path, ""))
                    break

                couples.append(("", ir_image.image_path))
                j += 1

            if j == len(self.all_ir_images):
                if i == len(self.all_rgb_images):
                    break
                couples.append((rgb_image.image_path, ""))
            i += 1

            self.couples_path_list = couples


    def add_relative_altitude_to_not_mappable_images(self, rel_alt):
        for image in self.all_rgb_images:
            if image.exif_header.usable and not image.exif_header.gps_coordinate.manual_altitude:
                continue
            if image.exif_header.gps_coordinate.altitude is None \
                    or image.exif_header.gps_coordinate.altitude == 0 \
                    or image.exif_header.gps_coordinate.manual_altitude:
                image.exif_header.gps_coordinate.altitude = rel_alt
                image.exif_header.gps_coordinate.manual_altitude = True
                image.exif_header.reconsider_usability()