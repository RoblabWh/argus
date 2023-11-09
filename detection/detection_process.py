import json
import threading
from argparse import Namespace
import utils as u
from datahandler import DataHandler
from annotationhandler import AnnotationHandler
from inference_engine import InferenceEngine


class DetectionProcess(threading.Thread):

    def __init__(self, report_id, models, max_splits, image_folder, ann_path, device):
        self.device = device
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
        args = Namespace(
            img=None,
            out_file='result.jpg',
            create_coco=True,
            netfolders=self.netfolders,
            configs="",
            checkpoints="",
            inputfolder=self.image_folder,
            outfolders=[],
            ann_path=self.ann_path,
            extensions=['.jpg', '.png'],
            pattern='.',
            include_subdirs=False,
            score_thr=0.3,
            batch_size=5,
            split_images=True,
            max_splitting_steps=self.max_splits)
        print("args: ", str(args), flush=True)
        u.assert_arguments(args)

        print("init engine", flush=True)
        engine = InferenceEngine(device=self.device, out_folders=args.outfolders, configs=args.configs,
                                 checkpoints=args.checkpoints, network_folders=args.netfolders)

        # Init DataHandler
        print("init datahandler", flush=True)
        datahandler = DataHandler(args)
        if args.split_images:
            print("option --split_images is set, images will be split into tiles")
            datahandler.preprocess(int(args.max_splitting_steps))
        data = datahandler.get_image_paths_str()

        # Inference, sometimes the matplotlib backend crashes, then saving won't work. Try again.
        results = engine.inference_all(data, score_thr=args.score_thr, batch_size=args.batch_size)
        # print("results: ", str(results))
        if args.split_images:
            datahandler.postprocess_images(results=results)
        results = datahandler.merge_bboxes(results=results)

        # Create AnnotationFile from Results
        if args.create_coco:
            annotationhandler = AnnotationHandler(args)
            annotationhandler.create_empty_ann(datahandler.image_paths)
            annotationhandler.save_results_in_json(results)

        self.reformat_ann()

        self.done = True

    def build_model_paths_list(self, models):
        # TODO use models from args
        # return [f'./model_weights/{model}' for model in models]
        models = ['/detection/model_weights/rtmdet_x_8xb32-300e_coco/small_trained_correctbbx/']
        return models

    def reformat_ann(self):
        print('reformatting ann', self.ann_path, flush=True)
        data = None
        with open(self.ann_path, 'r') as json_file:
            data = json.load(json_file)

        print('found', len(data["annotations"]), 'objects')
        for category in data["categories"]:
            category["colorHSL"] = [(300 - int((category["id"] + 1) / len(data["categories"]) * 360)) % 360, 100, 50]

        with open(self.ann_path, 'w') as json_file:
            json.dump(data, json_file)
