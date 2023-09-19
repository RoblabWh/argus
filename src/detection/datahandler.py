import copy
import os
import sys
import shutil
import re
from tqdm import tqdm
import numpy as np
from pathlib import Path
import itertools
import mmcv
from argparse import Namespace


# import utils as u

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
        # sort images by name
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
            # Sort by name
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
                    new_image_path = self.preprocessed_img_folder / (image_path.stem + f'_{j}' + image_path.suffix)
                    self.remove_later.append(new_image_path)
                    mmcv.imwrite(image, new_image_path)
                    new_image_paths.append(new_image_path)
                    ids[splitted_images + j] = image.shape[:2]

                self.split_images[image_path] = ids
            else:
                new_image_paths.append(image_path)

        self.image_paths = new_image_paths

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

        for result in results:
            delete_later = []
            result_pred = result['predictions']
            for key in self.split_images:
                ids = list(self.split_images[key].keys())
                # get bounding boxes of the pairs
                bboxes = [np.array(result_pred[i].pred_instances.bboxes.cpu()) for i in ids]
                # merge the results of the split images
                merged_bbox = self.merge_results(key, bboxes, ids)
                # add the merged results to the original result
                result_pred[ids[0]].pred_instances.bboxes = merged_bbox
                keys_to_add.append(key)
                delete_later.append({'delete_ids': ids[1:]})

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
        # sort images by name
        self.image_paths.sort(key=lambda x: x.name)

        return results

    def merge_results(self, key, bboxes, ids):
        """
        Recursively merges the results of the split images into the original image.
        :param key: key of the original image
        :param bboxes: results from the inference
        :param ids: ids
        :return: merged results
        """

        # split ids into pairs of four
        _ids = [i for i in range(len(ids))]
        id_pairs = [_ids[x:x+4] for x in range(0, len(_ids), 4)]
        pairs = [ids[x:x+4] for x in range(0, len(ids), 4)]

        while len(pairs[0]) > 1:
            new_pairs = []
            new_bboxes = []
            collapse = []
            for i, pair in enumerate(pairs):
                pairboxes = [bboxes[j] for j in id_pairs[i]]
                _bboxes = self.merge_results_of_four(key, pairboxes, pair)
                new_bboxes.append(_bboxes)
                new_pairs.append(i)
                collapse.append(pair)
            pairs = [new_pairs[x:x+4] for x in range(0, len(new_pairs), 4)]
            bboxes = new_bboxes
            for i, pair in enumerate(collapse):
                new_height = self.split_images[key][pair[0]][0] + self.split_images[key][pair[2]][0]
                new_width = self.split_images[key][pair[0]][1] + self.split_images[key][pair[1]][1]
                for j in pair:
                    self.split_images[key].pop(j)
                self.split_images[key][i] = (new_height, new_width)
        return bboxes[0]

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

        for class_bboxes in bboxes[1]:
            for bbox in class_bboxes:
                # bbox = x1, y1, x2, y2
                bbox[0] += w_offset
                bbox[2] += w_offset

        new_bboxes = copy.deepcopy(bboxes[0])
        new_bboxes = [np.concatenate((new_bboxes[i], bboxes[1][i]), axis=0) for i in range(len(bboxes[0]))] # horizontal merge

        for class_bboxes in bboxes[2]:
            for bbox in class_bboxes:
                # bbox = x1, y1, x2, y2
                bbox[1] += h_offset
                bbox[3] += h_offset

        new_bboxes = [np.concatenate((new_bboxes[i], bboxes[2][i]), axis=0) for i in range(len(bboxes[0]))] # vertical merge

        for class_bboxes in bboxes[3]:
            for bbox in class_bboxes:
                # bbox = x1, y1, x2, y2
                bbox[0] += w_offset
                bbox[2] += w_offset
                bbox[1] += h_offset
                bbox[3] += h_offset

        new_bboxes = [np.concatenate((new_bboxes[i], bboxes[3][i]), axis=0) for i in range(len(bboxes[0]))] # horizontal merge

        return new_bboxes