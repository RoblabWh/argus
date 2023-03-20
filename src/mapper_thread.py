import threading
from image_processor import ImageProcessor
from src.image_mapper import ImageMapper


class MapperThread(threading.Thread):
    def __init__(self, fast_mapping, odm_mapping, report_id, map_resolution, file_names):
        self.fast_mapping = fast_mapping
        self.with_odm = odm_mapping
        self.report_id = report_id
        self.file_names = file_names


        self.progress_preprocess = 0
        self.progress_mapping = 0
        self.message = "Step 1/2: Preprocessing"
        self.mapping = False
        self.metadata_delivered = False
        self.image_mapper = ImageMapper("./static/uploads/", report_id)
        self.image_mapper.set_processing_parameters(map_width_px=map_resolution[0],
                                               map_height_px=map_resolution[1], with_odm=odm_mapping)
        self.ir = False
        self.flight_data = None
        self.camera_specs = None
        self.weather_data = None
        self.couples_path_list = []
        self.rgb_images = []
        self.ir_images = []
        self.rgb_short_paths = []
        self.ir_short_paths = []
        self.panos = []
        self.maps = []
        self.maps_placeholders = []
        self.maps_done = []
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
                else:
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
                self.map_odm = self.image_mapper.generate_odm_orthophoto(3001, self.rgb_short_paths,840)
                self.maps.append(self.map_odm)
                self.set_next_map_done()
                self.progress_mapping += 96 / self.number_of_maps
                if self.ir:
                    self.map_odm_ir = self.image_mapper.generate_odm_orthophoto(3001, self.ir_short_paths, ir=True)
                    self.maps.append(self.map_odm_ir)
                    self.set_next_map_done()
                    self.progress_mapping += 100 / self.number_of_maps

        self.progress_mapping = 100


    def preprocess(self):
        self.progress_preprocess = 2
        processor = ImageProcessor()
        processor.set_image_paths(self.file_names)
        processor.generate_images_from_paths()
        self.progress_preprocess = 10
        processor.sort_images()
        self.progress_preprocess = 30
        processor.filter_panos()
        self.progress_preprocess = 40
        processor.separate_ir_rgb()
        self.progress_preprocess = 50
        processor.generate_flight_trajectory()
        self.progress_preprocess = 55

        self.panos = processor.get_panos()
        self.couples_path_list = processor.couples_path_list
        self.rgb_images = processor.all_rgb_images
        self.ir_images = processor.all_ir_images
        self.rgb_short_paths = processor.rgb_short_paths
        self.ir_short_paths = processor.ir_short_paths
        self.flight_trajectory = processor.flight_trajectory
        print("flight trajectory: " + str(self.flight_trajectory))
        self.progress_preprocess = 58


        #next step: calculate metadata for report
        self.flight_data = processor.extract_flight_data()
        self.progress_preprocess = 70
        self.camera_specs = processor.extract_camera_specs()
        self.progress_preprocess = 80
        self.weather_data = processor.load_weather_data()
        self.progress_preprocess = 90

        if self.fast_mapping or self.with_odm:

            self.mappable = self.image_mapper.generate_map_elements_from_images(rgb_images=self.rgb_images, ir_images=self.ir_images)
            self.ir = self.image_mapper.has_ir
            self.number_of_maps = self.fast_mapping + self.with_odm + self.fast_mapping * self.ir + self.with_odm * self.ir

            print("number of maps: " + str(self.number_of_maps))
            print("mappeable: " + str(self.mappable))
            print("ir: " + str(self.ir))

            if len(self.ir_short_paths) > 0:
                self.ir_settings = self.image_mapper.get_ir_settings()

            maps = self.image_mapper.generate_placeholder_maps()
            self.maps_done = [False] * self.number_of_maps

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
        return self.flight_data, self.camera_specs, self.weather_data, self.maps_placeholders, self.rgb_short_paths, \
            self.ir_short_paths, self.ir_settings, self.panos, self.couples_path_list, self.flight_trajectory

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



