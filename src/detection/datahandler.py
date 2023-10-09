import copy
import os
import sys
import shutil
import re
from tqdm import tqdm
import numpy as np
from pathlib import Path
import itertools
from mmengine.structures import InstanceData
import mmcv
from argparse import Namespace
import utils as u

# New Imports
from torch.utils.data import Dataset
import cv2
import torch


class DataHandler(Dataset):

    def __init__(self, args):

        if args is None:
            args = Namespace(inputfolder=None, extensions=['.jpg', '.png'], pattern='', include_subdirs=True, batch_size=1, img=None, out_file=None)

        self.img = args.img
        self.out_file = args.out_file

        self.img_prefix = None
        if args.img is not None:
            self.img_prefix = str(Path(args.img).expanduser().parent)
        else:
            if args.inputfolder is not None:
                self.img_prefix = str(Path(args.inputfolder).expanduser())

        self.extensions = args.extensions
        self.pattern = args.pattern
        self.include_subdirs = args.include_subdirs

        self.input_path = None
        if args.inputfolder is not None:
            self.input_path = Path(args.inputfolder)

        self.image_paths = self.get_image_paths()
        self.image_paths.sort(key=lambda x: x.name)

        # For preprocessing
        self.overlap = 0
        self.preprocess_ = False
        self.preprocessed_img_folder = None
        self.split_images = None
        self.remove_later = None

    def __len__(self):
        return len(self.image_paths)

    def __getitem__(self, index):
        img_path = self.image_paths[index]

        return img_path.__str__()

    def yield_images(self):
        path = self.input_path.expanduser()
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

    def set_image_paths(self, image_paths):
        """
        Set the image paths and batches
        :param image_paths: list of image paths
        """
        self.image_paths = image_paths
        self.image_paths.sort(key=lambda x: x.name)
        self.img_prefix = str(Path(image_paths[0]).expanduser().parent)

    def get_image_paths(self):
        if self.img is not None:
            image_paths = [Path(self.out_file)]
            shutil.copy(self.img, image_paths[0])
        else:
            image_paths = list(self.yield_images())
            if len(image_paths) == 0:
                print("No images found in %s" % str(self.input_path))
                sys.exit(1)

        return image_paths

    def get_image_paths_str(self):
        return [path.__str__() for path in self.image_paths]

    ###### PREPROCESSING ######
    def preprocess(self):
        """
        Preprocess or do not preprocess. Does not preprocess on first call.
        But initializes self.image_paths and self.batches.
        :param preprocess: bool to preprocess or not to preprocess
        """
        self.preprocess_ = not self.preprocess_
        if self.preprocess_:
            self.preprocess_images()
        else:
            # Set/reset the image paths
            self.image_paths = self.get_image_paths()
            self.image_paths.sort(key=lambda x: x.name)

    def preprocess_images(self):
        """
        Preprocesses the images. This includes:
        - Splitting large images into smaller ones
        """
        if self.image_paths is None:
            raise ValueError('No image paths set. Use set_image_paths() to set them.')
        if self.img_prefix is None:
            raise ValueError('No image prefix set. Use set_image_paths() to set them.')

        # Create a new folder for the preprocessed images
        self.preprocessed_img_folder = Path(self.img_prefix) / 'preprocessed'
        if self.preprocessed_img_folder.exists():
            shutil.rmtree(self.preprocessed_img_folder)
        self.preprocessed_img_folder.mkdir()

        # Iterate over all images and look up if they are too large
        new_image_paths = []
        self.split_images = {}
        self.remove_later = []
        splitted_images = 0
        images = []

        for i, image_path in enumerate(self.image_paths):
            img = mmcv.imread(image_path)

            # Split the image into smaller ones
            splitted_images += len(images)
            images = self.split_image(img)
            if len(images) > 1:
                ids = {}
                for j, image in enumerate(images):
                    new_image_path = self.preprocessed_img_folder / (image_path.stem + f'_{j:02d}' + image_path.suffix)
                    self.remove_later.append(new_image_path)
                    mmcv.imwrite(image, new_image_path)
                    new_image_paths.append(new_image_path)
                    ids[splitted_images + j] = image.shape[:2]
                    #print(f'Split image {image_path} into {new_image_path} with id {splitted_images + j} = {image.shape[:2]}')

                self.split_images[image_path] = ids
                #print(f'Split image {image_path} into {len(images)} smaller images with ids: {ids}')
            else:
                new_image_paths.append(image_path)

        self.image_paths = new_image_paths
        self.image_paths.sort(key=lambda x: x.name)

    def split_image(self, image):
        """
        Splits the image if its too large, recursively checks if the new images are too large, too.
        :param image: image to split
        :return: list of images
        """
        h, w = image.shape[:2]
        if h > 1200 or w > 1200:
            images = self.split_image_into_four(image)
            new_images = []
            for image in images:
                new_images.extend(self.split_image(image))
            return new_images
        else:
            return [image]

    def split_image_into_four(self, image):
        """
        Splits a large image into four smaller ones.
        :param image: large image
        :return: list of four smaller images
        """
        h, w = image.shape[:2]
        h2 = h // 2
        w2 = w // 2
        return [image[:h2 + self.overlap, :w2 + self.overlap], image[:h2 + self.overlap, w2 - self.overlap:],
                image[h2 - self.overlap:, :w2 + self.overlap], image[h2 - self.overlap:, w2 - self.overlap:]]

    ###### POSTPROCESSING ######

    def postprocess_images(self, results):
        """
        Postprocesses the images. This includes:
        - Merging the bounding boxes of the split images into the original image
        - Deleting the preprocessed images
        :param results: results from the inference
        :return: merged results
        """
        # TODO Split images is problematic, because the ids are not the same as the original ones

        keys_to_add = []
        last_net = len(results) - 1

        for net_num, result in enumerate(results):
            delete_later = []
            result_pred = result['predictions']
            for key in self.split_images:
                ids = list(self.split_images[key].keys())
                # get bounding boxes of the pairs
                bboxes = [np.array(result_pred[i].pred_instances.bboxes.cpu()) for i in ids]
                labels = [np.array(result_pred[i].pred_instances.labels.cpu()) for i in ids]
                scores = [np.array(result_pred[i].pred_instances.scores.cpu()) for i in ids]
                # image_paths = [np.array(result_pred[i].img_path) for i in ids]
                # print(f'merging {image_paths}')
                # merge the results of the split images
                merged_bbox, merged_label, merged_score = self.merge_results(key, bboxes, labels, scores, ids)
                # add the merged results to the original result
                new_instance = InstanceData()
                new_instance.bboxes = merged_bbox
                new_instance.labels = merged_label
                new_instance.scores = merged_score
                result_pred[ids[0]].pred_instances = new_instance
                delete_later.append({'delete_ids': ids[1:]})
                if net_num == last_net:
                    keys_to_add.append(key)

            for i in reversed(range(len(delete_later))):
                delete_ids = delete_later[i]['delete_ids']
                for i in reversed(range(len(delete_ids))):
                    del result_pred[delete_ids[i]]

        # Delete the preprocessed images from the disk and the image paths
        shutil.rmtree(self.preprocessed_img_folder)
        new_image_paths = []
        for path in self.image_paths:
            if path not in self.remove_later:
                new_image_paths.append(path)
        for key in keys_to_add:
            new_image_paths.append(key)
        self.image_paths = new_image_paths
        self.image_paths.sort(key=lambda x: x.name)

        return results

    def already_found(self, bbox, bboxes):
        for idx, existing_bbox in enumerate(bboxes):
            iou = u.calc_iou(bbox, existing_bbox)
            if iou > 0.05:
                return True, idx
        return False, None

    def merge_bboxes(self, results):
        net_cnt = len(results)
        num_images = len(results[0]['predictions'])
        instances = []

        if net_cnt == 1:
            return results[0]

        for img_idx in range(num_images):
            bboxes = [results[net_idx]['predictions'][img_idx].pred_instances.bboxes for net_idx in range(net_cnt)]
            labels = [results[net_idx]['predictions'][img_idx].pred_instances.labels for net_idx in range(net_cnt)]
            scores = [results[net_idx]['predictions'][img_idx].pred_instances.scores for net_idx in range(net_cnt)]

            merged_bboxes = []
            merged_labels = []
            merged_scores = []

            for net_a, net_b in itertools.combinations(range(net_cnt), 2):
                for idx_a, bbox_a in enumerate(bboxes[net_a]):
                    for idx_b, bbox_b in enumerate(bboxes[net_b]):
                        # Only merge if they belong to the same class
                        if labels[net_a][idx_a] == labels[net_b][idx_b]:
                            iou = u.calc_iou(bbox_a, bbox_b)
                            if iou > 0.05:
                                merged_bbox = (bbox_a + bbox_b) / 2
                                found, _ = self.already_found(merged_bbox, merged_bboxes)
                                if not found:
                                    merged_bboxes.append(merged_bbox)
                                    merged_labels.append(labels[net_a][idx_a])
                                    merged_scores.append((scores[net_a][idx_a] + scores[net_b][idx_b]) / 2)

            new_instance = InstanceData()
            new_instance.bboxes = np.array(merged_bboxes)
            new_instance.labels = np.array(merged_labels)
            new_instance.scores = np.array(merged_scores)
            instances.append(new_instance)

        for img_idx in range(num_images):
            results[0]['predictions'][img_idx].pred_instances = instances[img_idx]

        return results[0]

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
            bboxes = [results[net_idx]['predictions'][img_idx].pred_instances.bboxes for net_idx in range(net_cnt)]
            labels = [results[net_idx]['predictions'][img_idx].pred_instances.labels for net_idx in range(net_cnt)]
            scores = [results[net_idx]['predictions'][img_idx].pred_instances.scores for net_idx in range(net_cnt)]
            # Iterate over all classes
            class_bboxes = [[bboxes[net_idx][class_idx] for net_idx in range(net_cnt)] for class_idx in range(num_classes)]
            new_bboxes = [np.ndarray((0, 5)) for _ in range(num_classes)]
            for net_a, net_b in itertools.combinations(net_ids, 2):
                for class_idx in range(num_classes):
                    for bbox_a in class_bboxes[class_idx][net_a]:
                        for bbox_b in class_bboxes[class_idx][net_b]:
                            iou = u.calc_iou(bbox_a, bbox_b)
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

    def merge_results(self, key, bboxes, labels, scores, ids):
        """
        Recursively merges the results of the split images into the original image.
        :param key: key of the original image
        :param bboxes: results from the inference
        :param ids: ids
        :return: merged results
        """

        # split ids into pairs of four
        _ids = [i for i in range(len(ids))]
        id_pairs = [_ids[x:x+4] for x in range(0, len(_ids), 4)] #[[0,1,2,3],[4,5,6,7], ...]
        pairs = [ids[x:x+4] for x in range(0, len(ids), 4)] # [[16,17,18,19],[20,21,22,23], ...]

        while len(pairs[0]) > 1:
            new_pairs = []
            new_bboxes = []
            new_labels = []
            new_scores = []
            collapse = []
            for i, pair in enumerate(pairs):
                pairboxes = [bboxes[j] for j in id_pairs[i]]
                pairlabels = [labels[j] for j in id_pairs[i]]
                pairscores = [scores[j] for j in id_pairs[i]]
                _bboxes = self.merge_results_of_four(key, pairboxes, pair)
                _labels = np.concatenate((pairlabels[0], pairlabels[1], pairlabels[2], pairlabels[3]), axis=0)
                _scores = np.concatenate((pairscores[0], pairscores[1], pairscores[2], pairscores[3]), axis=0)
                new_bboxes.append(_bboxes)
                new_labels.append(_labels)
                new_scores.append(_scores)
                new_pairs.append(i)
                collapse.append(pair)
            pairs = [new_pairs[x:x+4] for x in range(0, len(new_pairs), 4)]
            bboxes = new_bboxes
            labels = new_labels
            scores = new_scores
            for i, pair in enumerate(collapse):
                new_height = self.split_images[key][pair[0]][0] + self.split_images[key][pair[2]][0]
                new_width = self.split_images[key][pair[0]][1] + self.split_images[key][pair[1]][1]
                for j in pair:
                    self.split_images[key].pop(j)
                self.split_images[key][i] = (new_height, new_width)
        return bboxes[0], labels[0], scores[0]

    def merge_results_of_four(self, key, bboxes, pair):
        """
        Merges the results of four images into one.
        :param bboxes: results from the inference
        :param pair: pair to merge
        :return: merged results
        """

        sizes = [self.split_images[key][i] for i in pair]
        w_offset = sizes[0][1]
        h_offset = sizes[0][0]

        # Modify bboxes[1]
        bboxes[1][:, [0, 2]] += w_offset

        # Modify bboxes[2]
        bboxes[2][:, [1, 3]] += h_offset

        # Modify bboxes[3]
        bboxes[3][:, [0, 2]] += w_offset
        bboxes[3][:, [1, 3]] += h_offset

        # Concatenate bboxes
        new_bboxes = np.concatenate((bboxes[0], bboxes[1], bboxes[2], bboxes[3]), axis=0)

        return new_bboxes