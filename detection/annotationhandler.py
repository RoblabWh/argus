import mmcv
import numpy as np
from mmdet.registry import DATASETS
from mmdet.datasets import BaseDetDataset

from customcoco import CustomCOCO
from mmengine.config import Config
from pathlib import Path
import json
import os


class AnnotationHandler:

    def __init__(self, args, keep_coco_format=True):
        self.custom_coco = None
        self.ann_path = None
        self.config = None

        self.CLASSES = ('fire', 'vehicle', 'human')
        self.PALETTE = [(220, 20, 60), (119, 11, 32), (0, 0, 142)]

        # Stuff for Creation of an ANN File

        if args.img is not None:
            img_prefix = str(Path(args.img).expanduser().parent)
        else:
            if args.inputfolder is not None:
                img_prefix = str(Path(args.inputfolder).expanduser())
            else:
                img_prefix = None

        # Relevant config paths
        self.ann_path = args.ann_path #"code/results/ann.json"
        self.score_thr = args.score_thr
        # Just any config file will do
        self.config_path = '/detection/model_weights/rtmdet_x_8xb32-300e_coco/small_trained_correctbbx/rtmdet_x_8xb32-300e_coco.py'
        self.img_prefix = img_prefix

        # Load the config
        self.config = Config.fromfile(self.config_path)
        classes = ('fire', 'vehicle', 'human')
        changes = {
            'data_root': self.img_prefix,
            'train_dataloader.dataset.ann_file': self.ann_path,
            'train_dataloader.dataset.img_prefix': self.img_prefix,
            'train_dataloader.dataset.metainfo.classes': classes,
            'val_dataloader.dataset.ann_file': self.ann_path,
            'val_dataloader.dataset.img_prefix': self.img_prefix,
            'val_dataloader.dataset.metainfo.classes': classes,
            'test_dataloader.dataset.ann_file': self.ann_path,
            'test_dataloader.dataset.img_prefix': self.img_prefix,
            'test_dataloader.dataset.metainfo.classes': classes,
        }
        self.config.merge_from_dict(changes)
        self.classes = [{"id": 1, "name": "fire"},
                        {"id": 2, "name": "vehicle"},
                        {"id": 3, "name": "human"}]

        self.custom_coco = None
        self.keep_coco_format = keep_coco_format

    def create_empty_ann(self, image_paths):
        """
        Create an empty annotation file with the same structure as COCO
        :return: empty annotation file
        """
        # Get Basenames from PosixPaths and convert to list
        img_names = [str(Path(img_path).name) for img_path in image_paths]
        # Get Hight and Width from images
        img_sizes = [mmcv.imread(img_path).shape[:2] for img_path in image_paths]  # (h, w)
        # Create image dictonary with id, name, height and width
        images = [{"id": i, "file_name": img_name, "height": img_size[0], "width": img_size[1]} for
                  i, (img_name, img_size) in enumerate(zip(img_names, img_sizes))]

        ann = {"images": images, "annotations": [], "categories": self.classes}
        with open(self.ann_path, 'w') as json_ann_file:
            json.dump(ann, json_ann_file, ensure_ascii=False, indent=4)

        self.custom_coco = CustomCOCO(ann_file=self.ann_path, score_thr=self.score_thr, keep_coco_format=self.keep_coco_format)

    def save_results_in_json(self, results, out_folder='.'):
        """
        Save the results in a json file
        :param out_folder: folder where to save the json file
        :param results: results to save
        :return:
        """
        outpath = str(Path(out_folder).expanduser() / "result.json")
        self.custom_coco.results2json(results, outpath)
        outpath = str(Path(out_folder).expanduser() / "result.json.bbox.json")
        # open json file
        with open(outpath) as json_bbox_file:
            with open(self.ann_path) as json_ann_file:
                bbox = json.load(json_bbox_file)
                ann = json.load(json_ann_file)
                ann["annotations"] = bbox
            with open(self.ann_path, 'w') as json_ann_file:
                json.dump(ann, json_ann_file, ensure_ascii=False, indent=4)
        os.remove(outpath)