import threading
from pathlib import Path
import sys
import os
import shutil
import json
from PIL import Image
import numpy as np
from py360convert import e2p
from keyframes import Keyframes
import re
import cv2
import math
class ImageMapperProcess(threading.Thread):
    def __init__(self, image_folder, output_folder, extensions, fov, keyframe_json, report_id):
        self.image_folder = Path(image_folder)
        self.output_folder = Path(output_folder)
        self.extensions = extensions
        self.report_id = report_id
        self.message = "Step 1/2: Preprocessing"
        self.image_paths = self.get_image_paths()
        self.keyframe_manager = Keyframes()
        self.load_keyframe_data(keyframe_json)
        self.progress_preprocess = 0
        self.progress_mapping = 0
        self.done = False
        self.started = False
        self.map_shape = [4000,4000]
        self.preprocess_img_size = [1000,1000]
        self.overlap_factor = 0.8
        self.border = 600
        self.img_prefix = str(self.image_folder.expanduser())
        self.remove_later = None
        self.saved_trajectory = None
        self.saved_mapping_result = None
        self.fov = fov
        self.preprocessed_img_folder = None
        super().__init__()

    def yield_images(self):
        path = self.image_folder.expanduser()
        for root, dirs, files in os.walk(path):
            for file in files:
                basename = os.path.basename(file).lower()
                ext = os.path.splitext(basename)[-1].lower()
                basename = basename.replace(ext, '')
                if ext in self.extensions:
                    yield Path(os.path.join(root, file))

    def get_image_paths(self):
        image_paths = list(self.yield_images())
        if (len(image_paths)) == 0:
            print("No images found in %s" % str(self.image_folder))
            sys.exit(1)
        return image_paths

    def load_keyframe_data(self, keyframe_json):
        f = open(keyframe_json)
        data = json.load(f)
        for keyframe in data:
            self.keyframe_manager.updateKeyframe(keyframe['id'], keyframe['pose'])

    def get_translation_and_rotation_from_pose(self, pose):
        pose_matrix = np.matrix(np.reshape(pose, (4, 4)))
        inv = np.linalg.inv(pose_matrix)
        translation = (inv.item((0, 3)), inv.item((1, 3)), inv.item((2, 3)))
        rotation = np.array([[inv.item((0, 0)), inv.item((0, 1)), inv.item((0, 2)), 0],
                             [inv.item((1, 0)), inv.item((1, 1)), inv.item((1, 2)), 0],
                             [inv.item((2, 0)), inv.item((2, 1)), inv.item((2, 2)), 0],
                             [0, 0, 0, 1]])
        return translation, rotation

    def generate_image_from_equirectangular(self, pano):
        height, width = pano.shape[:2]
        u_deg = 0
        v_deg = -90
        if (height > self.preprocess_img_size[0]):
            height = self.preprocess_img_size[0]
        output_shape = [height, height]
        in_rot_deg = 0
        result = e2p(pano, self.fov, u_deg, v_deg, output_shape, in_rot_deg, mode="bilinear")
        return result

    def preprocess_images(self):
        self.remove_later = []
        if self.image_paths is None:
            raise ValueError('No image path is set')
        self.preprocessed_img_folder = Path(self.img_prefix) / 'preprocessed'
        if self.preprocessed_img_folder.exists():
            shutil.rmtree(self.preprocessed_img_folder)
        self.preprocessed_img_folder.mkdir()
        new_image_paths = []

        number_of_images_done = 0
        for image_path in self.image_paths:
            img = np.array(Image.open(image_path))
            output_array = self.generate_image_from_equirectangular(img)
            new_image_path = self.preprocessed_img_folder / (image_path.stem + image_path.suffix)
            output_image = Image.fromarray(output_array)
            output_image.save(new_image_path)
            new_image_paths.append(new_image_path)
            self.remove_later.append(new_image_path)
            number_of_images_done += 1
            self.progress_preprocess = number_of_images_done/len(self.image_paths)

        if self.progress_preprocess >= 100:
            self.progress_preprocess = 100

        self.image_paths = new_image_paths
        self.image_paths.sort(key=lambda path: int(re.findall("\\d+", str(path.stem))[0]))

    def unit_vector(self, vector):
        return vector / np.linalg.norm(vector)

    def getScaleFactorAndHeight(self):
        minX = 0
        minY = 0
        minZ = 0
        maxX = 0
        maxY = 0
        maxZ = 0
        for keyframe in self.keyframe_manager.getAllKeyframes():
            if (keyframe['pose'] is None) or (len(keyframe['pose']) != 16):
                continue
            translation, rotation = self.get_translation_and_rotation_from_pose(keyframe['pose'])
            if translation[0] < minX:
                minX = translation[0]
            elif translation[0] > maxX:
                maxX = translation[0]
            if translation[1] < minY:
                minY = translation[1]
            elif translation[1] > maxY:
                maxY = translation[1]
            if translation[2] < minZ:
                minZ = translation[2]
            elif translation[2] > maxZ:
                maxZ = translation[2]
        if (maxX - minX) > (maxZ - minZ):
            scaleFactor = (self.map_shape[0] - (2 * self.border)) / (maxX - minX)
        else:
            scaleFactor = (self.map_shape[0] - (2 * self.border)) / (maxZ - minZ)
        return scaleFactor, (minX, maxX), (-maxY,-minY), (minZ, maxZ)

    def analyseFlight(self, x_interval, z_interval, scaleFactor, save_trajectory = False):
        flight_distance = 0
        latest_center = None
        largest_distance = 0

        trajectory_output = np.zeros((self.map_shape[0], self.map_shape[1], 3), dtype=np.uint8)
        # calculations for the flight
        for image_path in self.image_paths:
            id = re.findall("\\d+", str(image_path.stem))[0]
            pose = self.keyframe_manager.getKeyframePose(int(id))
            if (pose is None) or (len(pose) != 16):
                continue
            translation, rotation = self.get_translation_and_rotation_from_pose(pose)
            positionCenterX = int((translation[0] - x_interval[0]) * scaleFactor + self.border)
            positionCenterY = int((-translation[2] + z_interval[1]) * scaleFactor + self.border)
            if latest_center is None:
                latest_center = (positionCenterX, positionCenterY)
            else:
                # get distance between new center and last center
                x_delta = positionCenterX - latest_center[0]
                y_delta = positionCenterY - latest_center[1]
                distance = math.sqrt(x_delta ** 2 + y_delta ** 2)
                flight_distance += distance
                if (distance > largest_distance):
                    largest_distance = distance
                cv2.line(trajectory_output, (int(latest_center[0]), int(latest_center[1])),
                         (int(positionCenterX), int(positionCenterY)), (255, 128, 0), 15)
                latest_center = (positionCenterX, positionCenterY)

        average_distance = flight_distance / len(
            self.keyframe_manager.getAllKeyframes())  # average distance between two keyframes
        if(save_trajectory):
            alpha2 = np.sum(trajectory_output, axis=-1) > 0
            alpha2 = np.uint8(alpha2 * 255)
            trajectory_output = cv2.cvtColor(trajectory_output, cv2.COLOR_RGB2RGBA)
            trajectory_output[:, :, 3] = alpha2
            trajectory_file = self.output_folder / 'trajectory.png'
            cv2.imwrite(str(trajectory_file), trajectory_output)
            self.saved_trajectory = str(trajectory_file)
        return average_distance, largest_distance

    def cropImage(self, top, left, image):
        if (top < 0):
            crop = -top
            image = image[crop:image.shape[0], left:image.shape[1]]
            top += crop
        if (left < 0):
            crop = -left
            image = image[top:image.shape[0], crop:image.shape[1]]
            left += crop
        if (top + image.shape[1] > self.map_shape[1]):
            crop = (top + image.shape[1]) - self.map_shape[1]
            image = image[0:image.shape[0], 0:image.shape[1] - crop]
        if (left + image.shape[0] > self.map_shape[0]):
            crop = (left + image.shape[0]) - self.map_shape[0]
            image = image[0:image.shape[0] - crop, 0:image.shape[1]]
        return image, top, left

    def run(self):
        self.started = True
        self.preprocess_images()
        self.message = "Step 2/2: Mapping"
        #test code to load images, so it doesnt calculate them again (takes rly long)
        #self.preprocessed_img_folder = Path(self.img_prefix) / 'preprocessed'
        #self.image_folder = self.preprocessed_img_folder
        #self.yield_paths = self.yield_images()
        #self.image_paths = []
        #for image_path in self.yield_paths:
        #    self.image_paths.append(Path(image_path))
        #self.image_paths.sort(key=lambda path: int(re.findall("\\d+", str(path.stem))[0]))#sorting image_paths based on id
        #end testcode

        #calculate max and min positions for keyframe poses#
        scaleFactor, x_interval, y_interval, z_interval = self.getScaleFactorAndHeight()

        average_distance, largest_distance = self.analyseFlight(x_interval, z_interval, scaleFactor, save_trajectory=True)

        large_chunk_size = (largest_distance)*(1+(self.overlap_factor))

        #converts points in keyframe coordinatesystem to pixels on image
        output_map = np.zeros((self.map_shape[0], (self.map_shape[1]), 3), dtype=np.uint8)
        img = None
        number_of_images_done = 0
        for image_path in self.image_paths:
            img = cv2.imread(str(image_path))
            id = re.findall("\\d+", str(image_path.stem))[0]
            number_of_images_done += 1
            self.progress_mapping = (number_of_images_done / len(self.image_paths)) * 0.95

            #calculate image position and orientation
            pose = self.keyframe_manager.getKeyframePose(int(id))
            if (pose is None) or (len(pose) != 16):
                continue
            translation, rotation = self.get_translation_and_rotation_from_pose(
                self.keyframe_manager.getKeyframePose(int(id)))
            positionCenterX = int((translation[0] - x_interval[0]) * scaleFactor + self.border)
            positionCenterY = int((-translation[2] + z_interval[1]) * scaleFactor + self.border)
            if (int(large_chunk_size * ((-translation[1] - y_interval[0]) / (y_interval[1] - y_interval[0]))) <= 0):
                continue
            map_size = (int(large_chunk_size * ((-translation[1] - y_interval[0]) / (y_interval[1] - y_interval[0]))),
                        int(large_chunk_size * ((-translation[1] - y_interval[0]) / (y_interval[1] - y_interval[0]))))

            top = int(positionCenterX - (map_size[0]/2))
            left = int(positionCenterY - (map_size[1]/2))
            test_vector = np.array([0,0,100,1]) #in keyframe coordinate system this should be a vector pointing directly into the field of view
            new_vector = np.linalg.inv(rotation).dot(test_vector)
            flat_vector = np.array([new_vector[0], new_vector[2]])
            flat_vector2 = np.array([0,100])
            #get angle between those two vectors
            fv_u = self.unit_vector(flat_vector)
            fv2_u = self.unit_vector(flat_vector2)
            angle = np.arccos(np.clip(np.dot(fv_u, fv2_u), -1.0, 1.0))
            if(flat_vector[0] > flat_vector2[0]):
                #angle is turning counterclockwise aka. mathematically positive
                angle = angle*180/math.pi
            else:
                #angle is turning clockwise aka. mathematically negative
                angle = -(angle*180/math.pi)
            #now we need the angle between new_vector and test_vector
            small_img = cv2.resize(img, map_size)
            small_img_pil = Image.fromarray(small_img)
            rotated_img = small_img_pil.rotate(angle, expand=True) #kinda weird to convert cv2 img to pil and back to have a more comfortable rotate function
            rotated_image = np.array(rotated_img)
            rotated_image, top, left = self.cropImage(top, left, rotated_image)
            #temp_map = np.zeros((self.map_shape[0], (self.map_shape[1]), 3), dtype=np.uint8)
            #temp_map[left:left + int(rotated_image.shape[0]), top:top + int(rotated_image.shape[1])] = rotated_image #front image
            #do alpha blending
            alpha = np.sum(rotated_image, axis=-1) > 0
            alpha = np.uint8(alpha*255)
            #rotated_image = cv2.cvtColor(rotated_image, cv2.COLOR_RGB2RGBA)
            #rotated_image[:,:,3] = alpha
            alpha_s = alpha/255.0
            alpha_l = 1.0 - alpha_s
            for c in range(0,3):
                output_map[left:left+int(rotated_image.shape[0]), top:top+int(rotated_image.shape[1]), c] = (alpha_s * rotated_image[:,:,c] +
                                                                                                          alpha_l * output_map[left:left+int(rotated_image.shape[0]), top:top+int(rotated_image.shape[1]), c])

        alpha = np.sum(output_map, axis=-1) > 0
        alpha = np.uint8(alpha*255)
        output_map = cv2.cvtColor(output_map, cv2.COLOR_RGB2RGBA)
        output_map[:,:,3] = alpha
        cv2.imwrite(str(self.output_folder /'output_map.png'), output_map)
        self.saved_mapping_result = str(self.output_folder /'output_map.png')
        #start attaching images to the map based on keyframe poses

        #delete preprocessed images and reset image_paths
        shutil.rmtree(self.preprocessed_img_folder)
        self.image_paths = []
        if self.progress_mapping >= 0.95:
            self.progress_mapping = 1

    def get_progress_preprocess(self):
        return self.progress_preprocess

    def get_progress_mapping(self):
        return self.progress_mapping

    def get_saved_mapping_result(self):
        return self.saved_mapping_result

    def get_saved_trajectory_result(self):
        if self.saved_trajectory is not None:
            return self.saved_trajectory
        else:
            return None