import json
import threading


from transformerPipeline.inference.datahandler import DataHandler
from transformerPipeline.inference.inference_engine import Inferencer


class DetectionProcess(threading.Thread):

    def __init__(self, report_id, models, max_splits, image_folder, ann_path, device):
        self.device = device #CURRENTLY NOT SUPPORTED #TODO FIX
        self.report_id = report_id
        self.max_splits = max_splits
        self.done = False
        self.started = False
        self.image_folder = image_folder #f'./projects/{self.report_id}/rgb'
        self.ann_path = ann_path #f'./projects/{self.report_id}/ann.json'
        self.netfolders = self.build_model_paths_list(models)
        super().__init__()

    def run(self):
        self.started = True

        datahandler = DataHandler()
        inferencer = Inferencer(score_thr=0.4)
        models = inferencer.which_models_are_available()
        for model in models:
            inferencer.add_model(model)

        # inputfolder = "/home/nex/Bilder/Datasets/micro-test/images"
        # inputlist = ["/home/nex/Bilder/Datasets/micro-test/images/001918.jpg",
        #              "/home/nex/Bilder/Datasets/micro-test/images/DJI_0875.JPG"]

        datahandler.set_image_paths(self.image_folder)

        datahandler.preprocess()
        data = datahandler.get_data()
        results = inferencer(data)
        result = datahandler.postprocess(results)
        datahandler.set_ann_path(self.ann_path)
        datahandler.save_annotation(result)

        #datahandler.show(result)
        self.reformat_ann()

        self.done = True

    def build_model_paths_list(self, models):
        # TODO use models from args
        # return [f'./model_weights/{model}' for model in models]
        # models = ['/detection/model_weights/rtmdet_x_8xb32-300e_coco/small_trained_correctbbx/']
        models = ['/detection/model_weights/original/defor-detr/best/']
        return models

    def reformat_ann(self):
        print('reformatting ann', self.ann_path, flush=True)
        data = None
        with open(self.ann_path, 'r') as json_file:
            data = json.load(json_file)

        print('found', len(data["annotations"]), 'objects')

        for image in data["images"]:
            image["file_name"] = image["file_name"].split("/")[-1]

        for category in data["categories"]:
            category["colorHSL"] = [(300 - int((category["id"] + 1) / len(data["categories"]) * 360)) % 360, 100, 50]

        #add a version tag to the json file
        data["version"] = 1.0

        with open(self.ann_path, 'w') as json_file:
            json.dump(data, json_file)
