import json
import multiprocessing
import time

import numpy as np
import cv2
import imutils

class Map:

    def __init__(self, map_elements, width, height, blending, px_per_m, optimize, ir=False):
        self.map_elements = map_elements
        self.width = width
        self.height = height
        self.blending = blending
        self.px_per_m = px_per_m
        self.optimize = optimize
        self.final_map = np.zeros((height,width, 4), np.uint8)
        self.ir_temp_map = np.zeros((height, width, 2), np.float32)
        self.ir = ir
        #self.final_map = 34 * np.ones((width, height, 4), np.uint8)
        #self.final_map [:, :, 3] = 255
        #self.final_map = 255 * np.ones((width, height, 4), np.uint8)
        #self.spreading_range = spreading_range
        self.cropped_map = None
        self.bounds = None

    def create_map(self):
        map_creation_time_start = time.time()

        self.chunk_size = 32
        print('mapping: creating chunks of size: ', self.chunk_size)
        map_elements_chunks = [self.map_elements[i:i + self.chunk_size] for i in range(0, len(self.map_elements), self.chunk_size)]

        map_creation_time_loading = time.time()
        self.add_images_to_map(map_elements_chunks)
        if self.ir:
            if self.ir_temp_map.min() == 0 and self.ir_temp_map.max() == 0:
                pass
            else:
                self.final_map = self.draw_map_from_temp_data_with_LUT(3)
        map_creation_time_mapping = time.time()
        # self.crop_map()
        self.draw_flight_trajectorie()
        map_creation_time_end = time.time()

        print("MAPPING TIME SUMMARY: ", "\n  loading:", str(map_creation_time_loading-map_creation_time_start),
              "\n  mapping:", str(map_creation_time_mapping - map_creation_time_loading),
              "\n  cropping:", str(map_creation_time_end-map_creation_time_mapping),
              "\n  total:", str(map_creation_time_end-map_creation_time_start))


        #self.crop_map()
        return self.final_map


    # def load_images_parallel(self):
    #     pool = multiprocessing.Pool(6)
    #     self.map_elements = pool.map(Map.load_image, self.map_elements.copy())
    #     pool.close()
    #     pool.join()

    def draw_map_from_temp_data(self):
        #scale ir_temp_map to fit final_map from 0 to 255
        max = np.max(self.ir_temp_map[:, :, 0])
        min = np.min(self.ir_temp_map[:, :, 0])
        print("max: ", max, "min: ", min, "shape: ", self.final_map.shape, flush=True)

        map_scaled = (self.ir_temp_map[:, :, 0] - min) / (max - min) * 255
        map_scaled = map_scaled.astype(np.uint8)

        map_scaled = cv2.cvtColor(map_scaled, cv2.COLOR_GRAY2BGRA)
        map_scaled[:, :, 3] = (self.ir_temp_map[:, :, 1] * 255).astype(np.uint8)

        map_scaled[:, :, 2] = map_scaled[:, :, 2]
        map_scaled[:, :, 1] = (map_scaled[:, :, 1] * map_scaled[:, :, 1] ) * (1/128)
        map_scaled[:, :, 0] = (map_scaled[:, :, 0] * map_scaled[:, :, 0] ) * (-1/128) + 128
        # map_scaled[:, :, 0] = map_scaled[:, :, 0] * (-1) + 255

        return map_scaled

    def draw_map_from_temp_data_with_LUT(self, lut):
        #load lut from "static/default/gradient_luts/gradient_lut_" + lut + ".json"
        lut = json.load(open("./static/default/gradient_luts/gradient_lut_" + str(lut) + ".json"))
        lut_len = len(lut)

        min = np.min(self.ir_temp_map[:, :, 0])
        max = np.max(self.ir_temp_map[:, :, 0])

        map_scaled = (self.ir_temp_map[:, :, 0] - min) / (max - min) * 255
        map_scaled = map_scaled.astype(np.uint8)

        #generate an matrix in the shape of the image and fill it with the color value of the LUT, by using the map_scaled dor the index
        map_scaled = np.array(lut)[map_scaled]
        # print("shape: ", map_scaled.shape, flush=True)
        map_scaled[:, :, 3] = (self.ir_temp_map[:, :, 1] * 255).astype(np.uint8)

        #swap color channels
        output_map = map_scaled.copy()
        output_map[:, :, 0] = map_scaled[:, :, 2]
        output_map[:, :, 2] = map_scaled[:, :, 0]

        return output_map



    def load_images_parallel(self, map_elements):
        pool = multiprocessing.Pool(6)
        map_elements = pool.map(Map.load_image, map_elements)
        pool.close()
        pool.join()
        return map_elements



    @staticmethod
    def load_image(map_element):
        #faster but looses more quality due to scaling before rotation
        image = map_element.get_image().get_matrix()
        ir = map_element.get_image().exif_header.ir
        rotated_image_projection = map_element.get_projected_image_dims_px()
        #rotated_image_bounds = map_element.get_image_bounds_px()
        (w, h) = rotated_image_projection['width'], rotated_image_projection['height']
         # print (rotated_rectangle.get_angle(), w, h, w1, h1, c)
        if ir:
             resized_image = cv2.resize(image, (w, h), interpolation=cv2.INTER_LINEAR)
        else:
             resized_image = cv2.resize(image, (w, h), interpolation=cv2.INTER_AREA)

        rotated_image = imutils.rotate_bound(resized_image, map_element.get_projected_image_dims_px()['rotation'])
        map_element.get_image().set_matrix(rotated_image)
        return map_element


    def add_images_to_map(self, map_elements_chunks):
        if self.optimize: #voronoi aenderung
            performance_factor = 1
            while True:
                performance_factor *= 2
                width = self.width / performance_factor
                height = self.height / performance_factor
                if width < 1000 and height < 1000:
                    break

            print("mapping: calculating voronoi with performance factor: ", performance_factor)
            self.write_out_image_px_centers_on_map_scaled(performance_factor)
            self.closest_index_voronoi = self.generate_voronoi_indices_scaled(performance_factor)

        try:
            for j, elements in enumerate(map_elements_chunks):
                print("mapping: working on chunk of size: ", len(elements))

                elements = self.load_images_parallel(elements)


                for i, map_element in enumerate(elements):
                    print("image \"", map_element.image.image_path, "\" loaded with size:", image.shape, flush=True)
                    image = map_element.get_image().get_matrix()

                    coordinate = map_element.get_image_bounds_px()['center']
                    coordinate = (coordinate[0], self.height - coordinate[1])

                    y_offset = int(coordinate[1] - image.shape[0]/2)
                    x_offset = int(coordinate[0] - image.shape[1]/2)
                    y1, y2 = y_offset, y_offset + image.shape[0]
                    x1, x2 = x_offset, x_offset + image.shape[1]




                    if self.optimize:
                        closest_in_aoi = self.closest_index_voronoi[y1:y2, x1:x2]
                        if image.shape[2] == 4:
                            closest_in_aoi = np.repeat(closest_in_aoi[:, :, np.newaxis], 4, axis=2)
                            combined_image = self.final_map[y1:y2, x1:x2, :]
                            combined_image = np.where(closest_in_aoi == i + (j * self.chunk_size), image,
                                                      combined_image)
                            self.final_map[y1:y2, x1:x2, :] = combined_image
                        else:
                            closest_in_aoi = np.repeat(closest_in_aoi[:, :, np.newaxis], 2, axis=2)
                            combined_image = self.ir_temp_map[y1:y2, x1:x2, :]
                            combined_image = np.where(closest_in_aoi == i + (j * self.chunk_size), image,
                                                      combined_image)
                            self.ir_temp_map[y1:y2, x1:x2, :] = combined_image
                    else:
                        alpha_s = image[:, :, 3] / 255.0
                        alpha_l = 1.0 - alpha_s
                        alpha = self.blending
                        beta = 1.0 - alpha

                        for c in range(0, 4):
                            a = alpha_s * image[:, :, c]
                            b = alpha_l * self.final_map[y1:y2, x1:x2, c]
                            alpha_image = ( a + b)
                            self.final_map[y1:y2, x1:x2, c] = (alpha * alpha_image[:, :] + beta * self.final_map[y1:y2, x1:x2, c])

                    map_element.get_image().set_matrix(None)

                #for c in range(0, 2):
                #    a =  0.5 * image[:, :, c]
                #    b = 0.5 * self.final_map[y1:y2, x1:x2, c]
                #    alpha_image = ( a + b)
                #    self.final_map[y1:y2, x1:x2, c] = (0.5 * alpha_image[:, :] + 0.5 * self.final_map[y1:y2, x1:x2, c])
        except Exception as e:
            print("mapping: error adding images to map: ", e)
            pass

    def write_out_image_px_centers_on_map_scaled(self, n_times_smaller):
        centers_x = list()
        centers_y = list()
        factor = 1/n_times_smaller
        for i, map_element in enumerate(self.map_elements):
            coordinate = map_element.get_projected_image_dims_px()['center']
            centers_x.insert(i, factor*coordinate[0])
            centers_y.insert(i, factor*(self.height - coordinate[1]))
        self.centers_x = np.asarray(centers_x)
        self.centers_y = np.asarray(centers_y)


    def generate_voronoi_indices_scaled(self, n_times_smaller):  # ,width, height, image_position_on_new_map):

        factor = 1/n_times_smaller

        indices_clostest = self.calculate_voronoi_diagram(int(self.width*factor), int(self.height*factor), self.centers_x, self.centers_y)
        indices_clostest = cv2.resize(indices_clostest.astype(np.float32), (self.width, self.height),interpolation= cv2.INTER_NEAREST)
        indices_clostest = indices_clostest.astype(np.uint64)

        return indices_clostest


    def calculate_voronoi_diagram(self, width, height, centers_x, centers_y):
        print("mapping:  calculating voronoi indices for width: ", width, " height: ", height)
        # Create grid containing all pixel locations in image
        x, y = np.meshgrid(np.arange(0, width), np.arange(0, height))

        # Find squared distance of each pixel location from each center: the (i, j, k)th
        # entry in this array is the squared distance from pixel (i, j) to the kth center.
        squared_dist = (x[:, :, np.newaxis] - centers_x[np.newaxis, np.newaxis, :]) ** 2 + \
                       (y[:, :, np.newaxis] - centers_y[np.newaxis, np.newaxis, :]) ** 2

        # Find closest center to each pixel location
        indices = np.argmin(squared_dist, axis=2)  # Array containing index of closest center

        return indices


    def draw_flight_trajectorie(self):
        self.crop_map()

    def crop_map(self):
        #min_x, max_x, min_y, max_y = self.get_min_and_max_coords()
        #self.bounds = min_x, max_x, min_y, max_y
        final_map_copy = self.final_map.copy()
        #final_map_copy = self.final_map
        self.cropped_map = final_map_copy #[int(final_map_copy.shape[0]-max_y):int(final_map_copy.shape[0]-min_y), int(min_x):int(max_x)]
        self.adjust_map_elments()

    def adjust_map_elments(self):
        pass
        # min_x, max_x, min_y, max_y = self.bounds
        # for map_element in self.map_elements:
        #     rect = map_element.get_rotated_rectangle()
        #     x, y = rect.get_center()
        #     new_x = int(x - min_x)
        #     new_y = int(y - min_y)
        #     rect.set_center((new_x, new_y))
        # x,y = self.map_elements[0].get_projected_image_dims_px()['center']
        #print("x, y:",x,y)
    
    def get_cropped_map(self):
        return self.cropped_map

    def get_bounds(self):
        return self.bounds

    def get_min_and_max_coords(self):
        min_x = float("inf")
        min_y = float("inf")
        max_x = float("-inf")
        max_y = float("-inf")

        for map_element in self.map_elements:
            r = map_element.get_rotated_rectangle()
            coords_lst = r.get_multipoint()
            #print(coords_lst)
            for coord in coords_lst.geoms:
                x, y = coord.x, coord.y
                if (min_x > x):
                    min_x = x

                if (min_y > y):
                    min_y = y

                if (max_x < x):
                    max_x = x

                if (max_y < y):
                    max_y = y
        #print(min_x, max_x, min_y, max_y)
        return min_x, max_x, min_y, max_y

    def generate_ODM_placeholder_map(self, path_to_images):
        text_img = cv2.imread('waiting_for_ODM_Text.png')

        width, height = self.cropped_map.shape[1], self.cropped_map.shape[0]
        #create a black image with the same size as the cropped map
        image = np.zeros((height, width, 3), np.uint8)
        image_bg = np.zeros((height, width, 3), np.uint8)
        image_bg[:, :] = (106, 96, 36)

        #scale text_image to fit image
        scale = min(width / text_img.shape[1], height / text_img.shape[0])
        new_size = (int(text_img.shape[1] * scale), int(text_img.shape[0] * scale))
        text_img = cv2.resize(text_img, new_size)
        #place text_image in the center of the black image and use text_image alpha cannel as a mask
        x_offset = int((width - text_img.shape[1]) / 2)
        y_offset = int((height - text_img.shape[0]) / 2)
        image[y_offset:y_offset+text_img.shape[0], x_offset:x_offset+text_img.shape[1], :] = text_img
        image = np.maximum(image_bg, image, image)
        return image

    def get_map_elements(self):
        return self.map_elements



