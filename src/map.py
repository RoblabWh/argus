import multiprocessing
import time

import numpy as np
import cv2
import imutils

class Map:

    def __init__(self, map_elements, width, height, blending, px_per_m, optimize):
        self.map_elements = map_elements
        self.width = width
        self.height = height
        self.blending = blending
        self.px_per_m = px_per_m
        self.optimize = optimize
        self.final_map = np.zeros((width, height, 4), np.uint8)
        #self.final_map = 34 * np.ones((width, height, 4), np.uint8)
        #self.final_map [:, :, 3] = 255
        #self.final_map = 255 * np.ones((width, height, 4), np.uint8)
        #self.spreading_range = spreading_range
        self.cropped_map = None
        self.bounds = None

    def create_map(self):
        map_creation_time_start = time.time()
        # self.load_images()
        self.load_images_parallel()
        # pool = multiprocessing.Pool(6)
        # self.map_elements = pool.map(Map.load_image, self.map_elements.copy())
        # pool.close()
        # pool.join()
        map_creation_time_loading = time.time()
        self.add_images_to_map()
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

    def load_images(self):
        #average_color_map = 0
        #j = 0
        for map_element in self.map_elements:
            image = map_element.get_image().get_matrix()
            rotated_rectangle = map_element.get_rotated_rectangle()
            (w, h) = rotated_rectangle.get_size()
            h1,w1,c = image.shape
            resized_image = cv2.resize(image, (w, h), cv2.INTER_NEAREST)
            rotated_image = imutils.rotate_bound(resized_image, -rotated_rectangle.get_angle())
            (h, w) = rotated_rectangle.get_shape()
            rotated_image = cv2.resize(rotated_image, (int(w), int(h)), cv2.INTER_NEAREST)
            map_element.get_image().set_matrix(rotated_image)            

            #average_color_map = average_color_map + np.average(image)
            #j = j + 1            
        #average_color_map = int(average_color_map / len(self.map_elements))    
        #self.final_map = self.final_map 

    def load_images_parallel(self):
        pool = multiprocessing.Pool(6)
        self.map_elements = pool.map(Map.load_image, self.map_elements.copy())
        pool.close()
        pool.join()

    @staticmethod
    def load_image(map_element):
        image = map_element.get_image().get_matrix()
        rotated_rectangle = map_element.get_rotated_rectangle()
        (w, h) = rotated_rectangle.get_size()
        h1, w1, c = image.shape
        # print (rotated_rectangle.get_angle(), w, h, w1, h1, c)
        resized_image = cv2.resize(image, (w, h), cv2.INTER_NEAREST)
        rotated_image = imutils.rotate_bound(resized_image, -rotated_rectangle.get_angle())
        (h, w) = rotated_rectangle.get_shape()
        rotated_image = cv2.resize(rotated_image, (int(w), int(h)), cv2.INTER_NEAREST)
        map_element.get_image().set_matrix(rotated_image)
        return map_element

    def add_images_to_map(self):
        if self.optimize: #voronoi aenderung
            self.write_out_image_px_centers_on_map_scaled(4)
            self.closest_index_voronoi = self.generate_voronoi_indices_scaled(4)

        try:
            for i, map_element in enumerate(self.map_elements):

                image = map_element.get_image().get_matrix()
                coordinate = map_element.get_rotated_rectangle().get_center()
    
                coordinate = (coordinate[0], self.height - coordinate[1])
    
                y_offset = int(coordinate[1] - image.shape[0]/2)
                x_offset = int(coordinate[0] - image.shape[1]/2)
                y1, y2 = y_offset, y_offset + image.shape[0]
                x1, x2 = x_offset, x_offset + image.shape[1]
                ###########################
                #alpha = self.blending
                #beta = 1.0 - alpha
                #self.final_map = cv2.addWeighted(image, alpha, self.final_map, beta, 0.0)
                #self.final_map = cv2.add(image, self.final_map)
                ###########################

                if self.optimize:
                    closest_in_aoi = self.closest_index_voronoi[y1:y2, x1:x2]
                    closest_in_aoi = np.repeat(closest_in_aoi[:, :, np.newaxis], 4, axis=2)
                    combined_image = self.final_map[y1:y2, x1:x2, :]
                    combined_image = np.where(closest_in_aoi == i, image, combined_image)

                    self.final_map[y1:y2, x1:x2, :] = combined_image
                else:
                    alpha_s = image[:, :, 3] / 255.0
                    alpha_l = 1.0 - alpha_s
                    alpha = self.blending
                    beta = 1.0 - alpha

                    for c in range(0, 4):
                        a = alpha_s * image[:, :, c]
                        #cv2.imshow('a'+str(c), a)
                        #cv2.waitKey(0)
                        b = alpha_l * self.final_map[y1:y2, x1:x2, c]
                        #cv2.imshow('b'+str(c), b)
                        #cv2.waitKey(0)
                        alpha_image = ( a + b)
                        #cv2.imshow('alpha_image'+str(c), alpha_image)
                        self.final_map[y1:y2, x1:x2, c] = (alpha * alpha_image[:, :] + beta * self.final_map[y1:y2, x1:x2, c])

                #for c in range(0, 2):
                #    a =  0.5 * image[:, :, c]
                #    b = 0.5 * self.final_map[y1:y2, x1:x2, c]
                #    alpha_image = ( a + b)
                #    self.final_map[y1:y2, x1:x2, c] = (0.5 * alpha_image[:, :] + 0.5 * self.final_map[y1:y2, x1:x2, c])
        except:
            pass

    def write_out_image_px_centers_on_map_scaled(self, n_times_smaller):
        centers_x = list()
        centers_y = list()
        factor = 1/n_times_smaller
        for i, map_element in enumerate(self.map_elements):
            coordinate = map_element.get_rotated_rectangle().get_center()
            centers_x.insert(i, factor*coordinate[0])
            centers_y.insert(i, factor*(self.height - coordinate[1]))
        self.centers_x = np.asarray(centers_x)
        self.centers_y = np.asarray(centers_y)


    def generate_voronoi_indices_scaled(self, n_times_smaller):  # ,width, height, image_position_on_new_map):

        factor = 1/n_times_smaller

        indices_clostest = self.calculate_voronoi_diagram(self.width*factor, self.height*factor, self.centers_x, self.centers_y)
        indices_clostest = cv2.resize(indices_clostest.astype(np.float32), (self.width, self.height),interpolation= cv2.INTER_NEAREST)
        indices_clostest =indices_clostest.astype(np.uint64)

        return indices_clostest


    def calculate_voronoi_diagram(self, width, height, centers_x, centers_y):
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

        #for i in range(len(self.map_elements)-1):
        #    coordinate_image_1 = self.map_elements[i].get_rotated_rectangle().get_center()
        #    coordinate_image_2 = self.map_elements[i+1].get_rotated_rectangle().get_center()
            
        #    coordinate_image_1 = (coordinate_image_1[0], self.height - coordinate_image_1[1]) 
        #    coordinate_image_2 = (coordinate_image_2[0], self.height - coordinate_image_2[1]) 

        #    cv2.arrowedLine(self.final_map, coordinate_image_1, coordinate_image_2, (255,0,0,128), int(self.width/1000), 8,0,0.1) 
            #cv2.circle(self.final_map, coordinate_image_1, self.spreading_range, (0,0,255,128), thickness=1, lineType=8, shift=0)
            #cv2.circle(self.final_map, coordinate_image_1,int(self.width/1000),(0,0,255,128),cv2.FILLED) 
        #last_coordinate = self.map_elements[-1].get_rotated_rectangle().get_center()
        #last_coordinate = (last_coordinate[0], self.height - last_coordinate[1])
        
        #first_coordinate = self.map_elements[0].get_rotated_rectangle().get_center()
        #first_coordinate = (first_coordinate[0], self.height - first_coordinate[1])

        #cv2.circle(self.final_map, first_coordinate, int(self.width/1000), (0,255,0,128), cv2.FILLED)
        #cv2.circle(self.final_map, last_coordinate, int(self.width/1000), (0,255,0,128), cv2.FILLED)
                

        self.crop_map()

        #cv2.line(self.final_map,(int(self.width*0.025),int(self.height-self.height * 0.015)),(int(self.width*0.15),int(self.height-self.height * 0.015)),(0,0,0),int(self.width/1000))
        #cv2.line(self.final_map,(int(self.width*0.025),int(self.height-self.height * 0.010)),(int(self.width*0.025),int(self.height-self.height * 0.020)),(0,0,0),int(self.width/1000))

        #cv2.line(self.final_map,(int(self.width*0.15),int(self.height-self.height * 0.010)),(int(self.width*0.15),int(self.height-self.height * 0.020)),(0,0,0),int(self.width/1000))
        #meter = (self.width * 0.15 - self.width * 0.025)*(1/self.px_per_m)
        #cv2.putText(self.final_map, str(int(meter))+'m',(int(self.width*0.05),int(self.height-self.height * 0.025)), cv2.FONT_HERSHEY_SIMPLEX, int(self.width/1000),(0,0,0),int(self.width/1000),cv2.LINE_AA)


    def crop_map(self):
        min_x, max_x, min_y, max_y = self.get_min_and_max_coords()
        self.bounds = min_x, max_x, min_y, max_y
        final_map_copy = self.final_map.copy()
        #final_map_copy = self.final_map
        self.cropped_map = final_map_copy[int(final_map_copy.shape[0]-max_y):int(final_map_copy.shape[0]-min_y), int(min_x):int(max_x)]
        self.adjust_map_elments()

    def adjust_map_elments(self):
        min_x, max_x, min_y, max_y = self.bounds
        for map_element in self.map_elements:
            rect = map_element.get_rotated_rectangle()
            x, y = rect.get_center()
            new_x = int(x - min_x)
            new_y = int(y - min_y)
            rect.set_center((new_x, new_y))
        x,y = self.map_elements[0].get_rotated_rectangle().get_center()
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



