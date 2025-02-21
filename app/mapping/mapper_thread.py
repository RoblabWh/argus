import threading

from .image_processor import ImageProcessor
from .image_mapper import ImageMapper


class MapperThread(threading.Thread):
    def __init__(self, project_manager, webodm_manager, fast_mapping, odm_mapping, with_plausibility, report_id, map_resolution, file_names, data):
        self.fast_mapping = fast_mapping
        self.with_odm = odm_mapping
        self.report_id = report_id
        self.file_names = file_names
        self.data = data
        self.project_manager = project_manager


        self.progress_preprocess = 0
        self.progress_mapping = 0
        self.message = "Step 1/2: Preprocessing"
        self.mapping = False
        self.metadata_delivered = False
        self.image_mapper = ImageMapper(project_manager, webodm_manager, report_id, map_width_px=map_resolution[0],
                                            map_height_px=map_resolution[1], with_odm=odm_mapping, check_plausibility=with_plausibility)
        self.ir = False
        self.flight_data = None
        self.camera_specs = None
        self.weather_data = None
        self.couples_path_list = []
        self.rgb_images = []
        self.ir_images = []
        self.panos = []
        self.maps = []
        self.maps_placeholders = []
        self.maps_done = []
        self.maps_sent = []
        self.flight_trajectory = []
        self.number_of_maps = self.fast_mapping + self.with_odm + self.fast_mapping * self.ir + self.with_odm * self.ir
        self.map_rgb = None
        self.map_ir = None
        self.map_odm = None
        self.map_odm_ir = None
        self.ir_settings = None
        self.mappable = False
        super().__init__()

    def run(self):
        print("run with n maps: " + str(self.number_of_maps))
        self.preprocess()
        if self.with_odm or self.fast_mapping:
            self.maps = []
            if self.fast_mapping:
                self.mapping = True
                self.progress_mapping = 4 / self.number_of_maps
                self.message = "Step 2/2: Mapping"
                if self.mappable:
                    self.map_rgb = self.image_mapper.calculate_map_RGB(self.report_id)
                    print("rgb map calculated", flush=True)
                else:
                    print("not mappable, creating Error Map!")
                    self.map_rgb = self.image_mapper.generate_error_map(self.rgb_images)
                self.maps.append(self.map_rgb)
                self.set_next_map_done()
                self.progress_mapping += 96 / self.number_of_maps
                if self.ir:
                    if self.mappable:
                        self.map_ir = self.image_mapper.calculate_map_IR(self.report_id)
                    else:
                        self.map_ir = self.image_mapper.generate_error_map(self.ir_images, ir=True)
                    self.maps.append(self.map_ir)
                    self.set_next_map_done()
                    self.progress_mapping += 100 / self.number_of_maps
            if self.with_odm:
                self.mapping = True
                self.progress_mapping += 4 / self.number_of_maps
                # print("RGB_PATHS: " + str([image.get_image_path() for image in self.rgb_images]))
                self.map_odm = self.image_mapper.generate_odm_orthophoto([image.get_image_path() for image in self.rgb_images],840)
                self.maps.append(self.map_odm)
                self.set_next_map_done()
                self.progress_mapping += 96 / self.number_of_maps
                if self.ir:
                    # print("IR_PATHS: " + str([image.get_image_path() for image in self.ir_images]))
                    self.map_odm_ir = self.image_mapper.generate_odm_orthophoto([image.get_image_path() for image in self.ir_images], ir=True)
                    self.maps.append(self.map_odm_ir)
                    self.set_next_map_done()
                    self.progress_mapping += 100 / self.number_of_maps

        self.progress_mapping = 100


    def preprocess(self):
        flight_data = []
        try:
            flight_data = self.data['flight_data']
        except:
            pass

        #alle images liste für liste durchgehen und aus temp. filenames entfernen, von den übrigen noch image objects erstellen


        self.progress_preprocess = 2

        rgb_images = self.project_manager.get_image_objects_rgb(self.report_id)
        ir_images = self.project_manager.get_image_objects_ir(self.report_id)
        pano_images = self.project_manager.get_image_objects_panos(self.report_id)

        processor = ImageProcessor(self.file_names, rgb_images, ir_images, pano_images)
        self.progress_preprocess = 5

        processor.generate_images_from_paths()
        self.progress_preprocess = 35

        processor.filter_images()
        self.progress_preprocess = 40

        manual_altitude = self.project_manager.get_manual_relative_alt(self.report_id)
        use_elevation_data = self.project_manager.get_use_elevation_data(self.report_id)
        processor.add_relative_altitude_to_not_mappable_images(use_elevation_data, manual_altitude)

        processor.sort_images()
        self.progress_preprocess = 50

        processor.generate_flight_trajectory()
        self.progress_preprocess = 60

        processor.find_couples()
        self.progress_preprocess = 70

        self.panos = processor.get_panos()
        self.couples_path_list = processor.couples_path_list
        self.rgb_images = processor.all_rgb_images
        self.ir_images = processor.all_ir_images
        self.flight_trajectory = processor.flight_trajectory
        #print("flight trajectory: " + str(self.flight_trajectory))
        self.progress_preprocess = 75

        # for rgb_img in self.rgb_images:
        #     print("rgb image: " + str(rgb_img.get_image_path()) + " " + str(rgb_img.exif_header.usable))


        #next step: calculate metadata for report
        self.flight_data = processor.extract_flight_data(flight_data)
        self.progress_preprocess = 80
        self.camera_specs = processor.extract_camera_specs()
        self.progress_preprocess = 85
        self.weather_data = processor.load_weather_data()
        self.progress_preprocess = 90

        if self.fast_mapping or self.with_odm:

            self.mappable = self.image_mapper.generate_map_elements_from_images(rgb_images=self.rgb_images, ir_images=self.ir_images)
            self.ir = self.image_mapper.has_ir
            self.number_of_maps = self.fast_mapping + self.with_odm + self.fast_mapping * self.ir + self.with_odm * self.ir

            # print("number of maps: " + str(self.number_of_maps))
            # print("mappeable: " + str(self.mappable))
            # print("ir: " + str(self.ir))

            if len(self.ir_images) > 0:
                self.ir_settings = self.image_mapper.get_ir_settings()

            maps = self.image_mapper.generate_placeholder_maps()
            self.maps_done = [False] * self.number_of_maps
            self.maps_sent = [False] * self.number_of_maps

            self.map_rgb = maps[0]
            self.map_ir = maps[1]
            self.map_odm = maps[2]
            self.map_odm_ir = maps[3]

            self.maps_placeholders = []
            if self.fast_mapping:
                self.maps_placeholders.append(self.map_rgb)
                if self.ir:
                    self.maps_placeholders.append(self.map_ir)
            if self.with_odm:
                self.maps_placeholders.append(self.map_odm)
                if self.ir:
                    self.maps_placeholders.append(self.map_odm_ir)

        self.progress_preprocess = 100

    def set_next_map_done(self):
        index = self.maps_done.index(False)
        self.maps_done[index] = True

    def get_progress_preprocess(self):
        return self.progress_preprocess

    def get_progress_mapping(self):
        return self.progress_mapping

    def get_results(self):
        return self.flight_data, self.camera_specs, self.weather_data, self.maps_placeholders, [image.get_image_path() for image in self.rgb_images], \
            [image.get_image_path() for image in self.ir_images], self.ir_settings, self.panos, self.couples_path_list, self.flight_trajectory

    def get_mapper(self):
        return self.image_mapper

    def get_message(self):
        return self.message

    def is_mapping(self):
        return self.mapping

    def get_map(self):
        return self.map_rgb

    def get_map_ir(self):
        return self.map_ir

    def get_map_odm(self):
        return self.map_odm

    def get_map_odm_ir(self):
        return self.map_odm_ir

    def get_maps(self):
        return self.maps

    def get_ir_settings(self):
        return self.ir_settings

    def get_maps_done(self):
        return self.maps_done

    def get_maps_sent(self):
        return self.maps_sent

    def update_maps_sent(self, index):
        self.maps_sent[index] = True
