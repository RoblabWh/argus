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
        self.flight_data = None
        self.map = None
        super().__init__()

    def run(self):
        self.preprocess()
        self.progress_mapping = 1
        self.mapping = True
        self.message = "Step 2/2: Mapping"
        self.map = self.image_mapper.map_images(self.report_id)
        self.progress_mapping = 100



    def preprocess(self):
        print("preprocess_asynchronous")
        self.progress_preprocess = 2
        self.image_mapper.preprocess_start(self.report_id)
        self.progress_preprocess = 15
        images = self.image_mapper.preprocess_read_selection(self.file_names)
        self.progress_preprocess = 70
        images = self.image_mapper.preprocess_sort_images(images)
        self.progress_preprocess = 80
        self.image_mapper.preprocess_filter_images(images)
        self.progress_preprocess = 95

        self.flight_data, self.camera_specs, self.weather, self.map = self.image_mapper.preprocess_calculate_metadata()#self.report_id, self.file_names)
        self.progress_preprocess = 100

    def get_progress_preprocess(self):
        return self.progress_preprocess

    def get_progress_mapping(self):
        return self.progress_mapping

    def get_results(self):
        return self.flight_data, self.camera_specs, self.weather, self.map

    def get_mapper(self):
        return self.image_mapper

    def get_message(self):
        return self.message

    def is_mapping(self):
        return self.mapping

    def get_map(self):
        return self.map
