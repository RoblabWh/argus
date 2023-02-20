import os
import sys
import shutil
import re
import piexif
from tqdm import tqdm
import numpy as np
from pathlib import Path
import json
import itertools
import mmcv
from argparse import Namespace

from detection.customCoco import CustomCOCO


class DataHandler():

    def __init__(self, config_path, ann_path, args=None):
        """
        Initializes the DataHandler class.
        :param config_path: Path to the config file
        :param ann_path: Path to the annotation file
        :param args: Namespace object. Must contain keys: inputfolder, extensions, pattern, include_subdirs, batch_size, img, out_file
        # Example:
        # from argparse import Namespace
        # args = Namespace(inputfolder='path/to/inputfolder' or None, extensions=['.jpg', '.png'], pattern='*', include_subdirs=True, batch_size=1, img=None, out_file='path/to/out_file')
        # out_file and img are optional and only used when processing a single image, if inputfolder is set they can be set to None.
        """

        if args is None:
            args = Namespace(inputfolder=None, extensions=['.jpg', '.png', '.JPG', '.PNG'], pattern='', include_subdirs=True, batch_size=1, img=None, out_file=None)

        if args.img is not None:
            img_prefix = str(Path(args.img).expanduser().parent)
        else:
            if args.inputfolder is not None:
                img_prefix = str(Path(args.inputfolder).expanduser())
            else:
                img_prefix = None

        # Relevant config paths
        self.ann_path = ann_path
        self.config_path = config_path
        self.img_prefix = img_prefix

        # Load the config
        self.config = mmcv.Config.fromfile(self.config_path)
        self.config.data.train.ann_file = self.ann_path
        self.config.data.train.img_prefix = self.img_prefix
        self.config.data.val.ann_file = self.ann_path
        self.config.data.val.img_prefix = self.img_prefix
        self.config.data.test.ann_file = self.ann_path
        self.config.data.test.img_prefix = self.img_prefix
        self.config.data_root = self.img_prefix
        self.config.CLASSES = ('fire', 'vehicle', 'human')
        self.classes = [{"id": 1, "name": "fire"},
                        {"id": 2, "name": "vehicle"},
                        {"id": 3, "name": "human"}]

        self.custom_coco = None

        # Relevant data paths
        self.img = args.img
        self.out_file = args.out_file

        if args.inputfolder is not None:
            self.inputpath = Path(args.inputfolder)
        else:
            self.inputpath = None

        self.extensions = args.extensions
        self.pattern = args.pattern
        self.include_subdirs = args.include_subdirs

        if self.inputpath is not None:
            self.image_paths = self.get_image_paths()
            # sort images by name
            self.image_paths.sort(key=lambda x: x.name)

            self.batches = [self.image_paths[x:x+args.batch_size] for x in range(0, len(self.image_paths), args.batch_size)]
        else:
            self.image_paths = None
            self.batches = None

    def set_image_paths(self, image_paths, batch_size):
        """
        Set the image paths and batches
        :param image_paths: list of image paths
        :param batch_size: batch size
        :return:
        """
        self.image_paths = image_paths
        # sort images by name
        #self.image_paths.sort(key=lambda x: x.name)
        self.batches = [self.image_paths[x:x+batch_size] for x in range(0, len(self.image_paths), batch_size)]

        self.img_prefix = str(Path(image_paths[0]).expanduser().parent)
        self.config.data.train.img_prefix = self.img_prefix
        self.config.data.val.img_prefix = self.img_prefix
        self.config.data.test.img_prefix = self.img_prefix
        self.config.data_root = self.img_prefix

    def create_coco(self):
        """
        Create a custom coco dataset from the config and load the annotations
        :return:
        """
        self.custom_coco = CustomCOCO(self.ann_path, self.config.test_pipeline, test_mode=True)
        self.custom_coco.load_annotations(self.ann_path)

    def create_empty_ann(self):
        """
        Create an empty annotation file with the same structure as COCO
        :return: empty annotation file
        """
        # Get Basenames from PosixPaths and convert to list
        img_names = [str(Path(img_path).name) for img_path in self.image_paths]
        # Get Hight and Width from images
        img_sizes = [mmcv.imread(img_path).shape[:2] for img_path in self.image_paths] # (h, w)
        # Create image dictonary with id, name, height and width
        images = [{"id": i, "file_name": img_name, "height": img_size[0], "width": img_size[1]} for i, (img_name, img_size) in enumerate(zip(img_names, img_sizes))]

        ann = {}
        ann["images"] = images
        ann["annotations"] = []
        ann["categories"] = self.classes
        with open(self.ann_path, 'w') as json_ann_file:
            json.dump(ann, json_ann_file, ensure_ascii=False, indent=4)

    def apply_threshold_to_results(self, all_results, score_thr):
        """
        Apply a threshold to the results
        :param all_results: list of results to apply the threshold to
        :return:
        """
        for results in all_results:
            for i, image in enumerate(results):
                for j, bboxes in enumerate(image):
                    scores = bboxes[:, -1]
                    inds = scores > score_thr
                    results[i][j] = bboxes[inds]

    def iou(self, bbox1, bbox2):
        """
        Calculates the IoU for two bounding boxes
        :param bbox1: bounding box 1
        :param bbox2: bounding box 2
        :return: IoU
        """
        x1 = max(bbox1[0], bbox2[0])
        y1 = max(bbox1[1], bbox2[1])
        x2 = min(bbox1[2], bbox2[2])
        y2 = min(bbox1[3], bbox2[3])
        w = max(0, x2 - x1)
        h = max(0, y2 - y1)
        inter = w * h
        area1 = (bbox1[2] - bbox1[0]) * (bbox1[3] - bbox1[1])
        area2 = (bbox2[2] - bbox2[0]) * (bbox2[3] - bbox2[1])
        union = area1 + area2 - inter
        iou = inter / union
        return iou

    def allready_found(self, bbox, found_bboxes):
        """
        Check if a bounding box is allready found
        :param bbox: bounding box to check
        :param found_bboxes: bounding boxes that are allready found
        :return: True if allready found, False if not
        """
        for i, found_bbox in enumerate(found_bboxes):
            if self.iou(bbox, found_bbox) > 0.5:
                return True, i
        return False, None

    def compare_results(self, results):
        """
        Calculates the IoU for all results and returns new bounding boxes where the bounding boxes match
        :param results: results bounding boxes to calculate the IoU for
        :return: new matching bounding boxes
        """
        net_cnt = len(results)
        net_ids = list(range(net_cnt))
        num_images = len(results[0])
        num_classes = len(self.config.CLASSES)
        new_results = [[] for _ in range(num_images)]
        if net_cnt == 1:
            return results[0]
        # Iterate over all images
        for img_idx in range(num_images):
            # Get every bbox for this image
            bboxes = [results[net_idx][img_idx] for net_idx in range(net_cnt)]
            # Iterate over all classes
            class_bboxes = [[bboxes[net_idx][class_idx] for net_idx in range(net_cnt)] for class_idx in range(num_classes)]
            new_bboxes = [np.ndarray((0, 5)) for _ in range(num_classes)]
            for net_a, net_b in itertools.combinations(net_ids, 2):
                for class_idx in range(num_classes):
                    for bbox_a in class_bboxes[class_idx][net_a]:
                        for bbox_b in class_bboxes[class_idx][net_b]:
                            iou = self.iou(bbox_a, bbox_b)
                            if iou > 0.1:
                                # check if bbox allready found by other nets
                                bbox = (bbox_a + bbox_b) / 2
                                found, _idx = self.allready_found(bbox_a, new_bboxes[class_idx])
                                # TODO maybe update bbox if it was found by other nets
                                if not found:
                                    # add new bbox
                                    new_bboxes[class_idx] = np.append(new_bboxes[class_idx], [bbox], axis=0)
            new_results[img_idx] = new_bboxes
        return new_results

    def save_results_in_json(self, results):
        """
        Save the results in a json file
        :param out_folder: folder where to save the json file
        :param results: results to save
        :return:
        """
        # print("Saving results in json file")
        out_folder = '.'
        outpath = str(Path(out_folder).expanduser() / "result.json")
        self.custom_coco.results2json(results, outpath)
        outpath = str(Path(out_folder).expanduser() / "result.json.bbox.json")
        # open json file
        # print("outpath: %s" % outpath)
        # print("ann_path: %s" % self.ann_path)
        with open(outpath) as json_bbox_file:
            with open(self.ann_path) as json_ann_file:
                bbox = json.load(json_bbox_file)
                ann = json.load(json_ann_file)
                ann["annotations"] = bbox
            with open(self.ann_path, 'w') as json_ann_file:
                json.dump(ann, json_ann_file, ensure_ascii=False, indent=4)
        os.remove(outpath)

    def structure_ann_by_images(self):
        """
        opens the ann json file and structures it by images
        then saves as a new json file with the name suffix _structured
        """
        # open json file
        with open(self.ann_path) as json_ann_file:
            ann = json.load(json_ann_file)
            images = ann["images"]
            annotations = ann["annotations"]
            ann_by_images = {}
            for image in images:
                ann_by_images[image["id"]] = []
            for annotation in annotations:
                ann_by_images[annotation["image_id"]].append(annotation)
            ann["annotations"] = ann_by_images
            # add an etntry to each category that tells the sum of its annotations
            for category in ann["categories"]:
                category["sum"] = 0
                category["lowest_score"] = 1
            # add an entry to each categorie that tells the sum of all its appearances in the annotations
            # also add an entry to each categorie that tells the lowest score of all its appearances in the annotations
            for image_id in ann["annotations"]:
                for annotation in ann["annotations"][image_id]:
                    category_id = annotation["category_id"]
                    category = ann["categories"][category_id - 1]
                    category["sum"] += 1
                    if annotation["score"] < category["lowest_score"]:
                        category["lowest_score"] = annotation["score"]
            # add an entry to each image that tells the sum of all its annotations per category
            for image in images:
                image["sum"] = []
                for category in ann["categories"]:
                    image["sum"].append(0)
                for annotation in ann["annotations"][image["id"]]:
                    category_id = annotation["category_id"]
                    image["sum"][category_id - 1] += 1

        # save json file
        with open(self.ann_path, 'w') as json_ann_file:
            json.dump(ann, json_ann_file, ensure_ascii=False, indent=4)


    def get_image_paths(self):
        if self.img is not None:
            image_paths = [Path(self.out_file)]
            shutil.copy(self.img, image_paths[0])
        else:
            image_paths = list(self.yield_images())
            if len(image_paths) == 0:
                print("No images found in %s" % str(self.inputpath))
                sys.exit(1)

        return image_paths

    def yield_images(self):
        path = self.inputpath.expanduser()
        for root, dirs, files in os.walk(path):
            for file in files:
                basename = os.path.basename(file).lower()
                ext = os.path.splitext(basename)[-1].lower()
                basename = basename.replace(ext, '')
                if ext in self.extensions and bool(re.compile(self.pattern).match(basename)):
                    if self.include_subdirs:
                        yield Path(os.path.join(root, file))
                    elif root == str(path):
                        yield Path(os.path.join(root, file))

    def save_images(self, out_folder, results, model, score_thr):
        """
        Saves the images with the bounding boxes drawn on them. The EXIF data is copied from
        the original image to the new image.
        :param out_folder: folder where to save the images
        :param results: results to draw on the images, usually results[i] for model[i]
        :param model: model to draw the results on the images
        """
        if out_folder:
            outfiles = []
            for i, image_path in enumerate(tqdm(self.image_paths, desc='Saving pictures...')):
                image_path = Path(image_path)
                output_path = str(image_path.resolve()).replace(str(image_path.resolve().parent), str(Path(out_folder).expanduser()))
                outfiles.append(output_path)
                model.show_result(image_path, results[i], out_file=output_path, score_thr=score_thr)
                try:
                    piexif.transplant(str(image_path), output_path)
                except ValueError:
                    print("\nNo EXIF Data found in %s saving without EXIF Data" % image_path)
