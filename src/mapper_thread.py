import threading
import time


class MapperThread(threading.Thread):
    def __init__(self, image_mapper, report_id, file_names):
        self.progress_preprocess = 0
        self.progress_mapping = 0
        self.message = "Step 1/2: Preprocessing"
        self.mapping = False
        self.metadata_delivered = False
        self.image_mapper = image_mapper
        self.report_id = report_id
        self.file_names = file_names
        self.odm = image_mapper.with_ODM
        self.ir = image_mapper.CONTAINED_DJI_INFRARED_IMAGES
        self.flight_data = None
        self.maps = []
        self.maps_done = []
        self.map_rgb = None
        self.map_ir = None
        self.map_odm = None
        self.map_odm_ir = None
        self.number_of_maps = 1 + self.odm + self.ir + self.odm * self.ir
        self.ir_settings = None
        self.panos = []
        super().__init__()

    def run(self):
        print("run with n maps: " + str(self.number_of_maps))
        self.preprocess()
        self.progress_mapping = 4/ self.number_of_maps
        self.mapping = True
        self.message = "Step 2/2: Mapping"
        self.map_rgb = self.image_mapper.calculate_map_RGB(self.report_id)
        self.maps = []
        self.maps.append(self.map_rgb)
        self.set_next_map_done()
        self.progress_mapping = 100 / self.number_of_maps
        if self.ir:
            self.map_ir = self.image_mapper.calculate_map_IR(self.report_id)
            self.maps.append(self.map_ir)
            self.set_next_map_done()
            self.progress_mapping += 100 / self.number_of_maps
        if self.odm:
            self.map_odm = self.image_mapper.generate_odm_orthophoto(3001, 840)
            self.maps.append(self.map_odm)
            self.set_next_map_done()
            self.progress_mapping += 100 / self.number_of_maps
            if self.ir:
                self.map_odm_ir = self.image_mapper.generate_odm_orthophoto(3001, ir=True)
                self.maps.append(self.map_odm_ir)
                self.set_next_map_done()
                self.progress_mapping += 100 / self.number_of_maps

        self.progress_mapping = 100


    def preprocess(self):
        print("preprocess_asynchronous")
        self.progress_preprocess = 2
        self.image_mapper.preprocess_start(self.report_id)
        self.progress_preprocess = 15
        images = self.image_mapper.preprocess_read_selection(self.file_names)
        self.progress_preprocess = 50
        images = self.image_mapper.preprocess_sort_images(images)
        self.progress_preprocess = 70
        self.image_mapper.preprocess_filter_images(images)
        self.panos = self.image_mapper.get_panos()
        self.progress_preprocess = 85

        self.flight_data, self.camera_specs, self.weather, maps, self.rgb_files, self.ir_files =\
            self.image_mapper.preprocess_calculate_metadata()

        self.odm = self.image_mapper.with_ODM
        self.ir = self.image_mapper.CONTAINED_DJI_INFRARED_IMAGES
        self.number_of_maps = 1 + self.odm + self.ir + self.odm * self.ir
        self.maps_done = [False] * self.number_of_maps

        self.map_rgb = maps[0]
        self.map_ir = maps[1]
        self.map_odm = maps[2]
        self.map_odm_ir = maps[3]

        self.maps = []
        self.maps.append(self.map_rgb)
        if self.ir:
            self.maps.append(self.map_ir)
        if self.odm:
            self.maps.append(self.map_odm)
            if self.ir:
                self.maps.append(self.map_odm_ir)

        self.ir_settings = self.image_mapper.get_ir_settings()
        self.progress_preprocess = 100

    def set_next_map_done(self):
        index = self.maps_done.index(False)
        self.maps_done[index] = True

    def get_progress_preprocess(self):
        return self.progress_preprocess

    def get_progress_mapping(self):
        return self.progress_mapping

    def get_results(self):
        return self.flight_data, self.camera_specs, self.weather, self.maps, self.rgb_files, self.ir_files, \
            self.ir_settings, self.panos

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

