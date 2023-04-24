import multiprocessing
import time

import numpy as np
import cv2
import imutils

from src.map_element_v2 import MapElement
class Map_v2:
    def __init__(self, map_elements, map_size):
        self.map_elements = map_elements
        self.map_size = map_size
        self.map = None
        self.chunk_size = 16


    def generate_map(self):
        map_elements = self.map_elements
        self.calculate_pixel_position(map_elements, self.map_size)
        self.map = np.zeros((self.height, self.width, 4), np.uint8)

        print('mapping: creating chunks of size: ', self.chunk_size)
        map_elements_chunks = [self.map_elements[i:i + self.chunk_size] for i in
                               range(0, len(self.map_elements), self.chunk_size)]

        self.build_map(map_elements_chunks)
        return self.map

    def calculate_pixel_position(self, map_elements, map_size):
        # Find the minimum and maximum latitude and longitude values among all map elements
        min_lat, max_lat, min_lon, max_lon = float('inf'), float('-inf'), float('inf'), float('-inf')
        for element in map_elements:
            for gps_corner in element.gps_corners:
                if gps_corner.latitude < min_lat:
                    min_lat = gps_corner.latitude
                if gps_corner.latitude > max_lat:
                    max_lat = gps_corner.latitude
                if gps_corner.longitude < min_lon:
                    min_lon = gps_corner.longitude
                if gps_corner.longitude > max_lon:
                    max_lon = gps_corner.longitude

        # Calculate the scale based on the longest side of the map
        map_range = max(max_lon - min_lon, max_lat - min_lat)
        scale = map_size / map_range
        self.width = int((max_lon - min_lon) * scale)
        self.height = int((max_lat - min_lat) * scale)

        # Calculate the pixel position for each corner of each map element
        for element in map_elements:
            px_corners = []
            for gps_corner in element.gps_corners:
                # Calculate the relative position of the GPS coordinate on the map
                rel_lat = (gps_corner.latitude - min_lat) * scale
                rel_lon = (gps_corner.longitude - min_lon) * scale

                # Calculate the pixel position on the map
                x = int(rel_lon)
                y = int(self.height - rel_lat)

                # Save the pixel position in the map element
                px_corners.append((x, y))
            element.set_px_corners(px_corners)

        self.plot_px_corners(map_elements)
        self.plot_gps_corners(map_elements)





    @staticmethod
    def warp_image(map_element):
        # Define the source and target corners for the perspective transform
        # src_corners = np.float32(
        #     [[0, map_element.get_image().get_height()],
        #      [map_element.get_image().get_width(), map_element.get_image().get_height()],
        #      [map_element.get_image().get_width(), 0],
        #      [0, 0]])
        src_corners = np.float32(
            [[0, 0],
             [map_element.get_image().get_width(), 0],
             [map_element.get_image().get_width(), map_element.get_image().get_height()],
             [0, map_element.get_image().get_height()]])
        px_corners_local = map_element.px_corners
        # find max x and maxy and suptract from corners
        min_x = 100000
        min_y = 100000
        for corner in px_corners_local:
            if corner[0] < min_x:
                min_x = corner[0]
            if corner[1] < min_y:
                min_y = corner[1]

        for i, corner in enumerate(px_corners_local):
            px_corners_local[i] = (corner[0] - min_x, corner[1] - min_y)


        dst_corners = np.float32(px_corners_local)

        # Calculate the perspective transform matrix
        M = cv2.getPerspectiveTransform(src_corners, dst_corners)

        # Warp the image using the perspective transform
        warped_image = cv2.warpPerspective(map_element.get_image().get_matrix(), M,
                                           (map_element.px_width, map_element.px_height))

        # Save the warped image in the map element
        map_element.get_image().set_matrix(warped_image)
        map_element.set_dims(warped_image.shape[1], warped_image.shape[0])

        return map_element

    def load_and_warp_parallel(self, map_elements):
        pool = multiprocessing.Pool(6)
        map_elements = pool.map(Map_v2.warp_image, map_elements)
        pool.close()
        pool.join()
        return map_elements

    def build_map(self, map_elements_chunks):

        performance_factor = 1
        while True:
            performance_factor *= 2
            width = self.width / performance_factor
            height = self.height / performance_factor
            if width < 1000 and height < 1000:
                break

        print("mapping: calculating voronoi with performance factor: ", performance_factor)
        self.scale_image_centers_for_fast_voronoi(performance_factor)
        self.closest_index_voronoi = self.generate_voronoi_indices_scaled(performance_factor)

        # try:
        for j, elements in enumerate(map_elements_chunks):
            print("mapping: working on chunk of size: ", len(elements))

            elements = self.load_and_warp_parallel(elements)

            for i, map_element in enumerate(elements):
                warped_image = map_element.get_image().get_matrix()
                # save warped image in /static/debug
                cv2.imwrite("static/debug/warped_image_" + str(i) + ".png", warped_image)
                self.add_image_to_map(warped_image, map_element.px_center,
                                      map_element.px_width, map_element.px_height,
                                      i + (j * self.chunk_size))
                map_element.get_image().set_matrix(None)

        cv2.imwrite("static/debug/map.png", self.map)
        self.save_voronoi()

        # except:
        #     print("mapping: error in build_map")

        return self.map

    def scale_image_centers_for_fast_voronoi(self, n_times_smaller):
        centers_x = list()
        centers_y = list()
        factor = 1 / n_times_smaller
        for i, map_element in enumerate(self.map_elements):
            coordinate = map_element.px_center
            centers_x.insert(i, factor * coordinate[0])
            centers_y.insert(i, factor * (self.height - coordinate[1]))
        self.centers_x = np.asarray(centers_x)
        self.centers_y = np.asarray(centers_y)



    def add_image_to_map(self, image, center, width, height, index):
        half_width = int(width / 2)
        half_height = int(height / 2)
        x1 = center[0] - half_width
        x2 = center[0] + half_width
        y1 = center[1] - half_height
        y2 = center[1] + half_height

        if x2 - x1 < image.shape[1] :
            if x1 > 0:
                x1 = x1-1
            else:
                x2 = x2+1

        if y2 - y1 < image.shape[0] :
            if y1 > 0:
                y1 = y1-1
            else:
                y2 = y2+1

        closest_in_aoi = self.closest_index_voronoi[y1:y2, x1:x2]
        closest_in_aoi = np.repeat(closest_in_aoi[:, :, np.newaxis], 4, axis=2)
        combined_image = self.map[y1:y2, x1:x2, :]
        combined_image = np.where(closest_in_aoi == index, image, combined_image)

        self.map[y1:y2, x1:x2, :] = combined_image

    def generate_voronoi_indices_scaled(self, n_times_smaller):  # ,width, height, image_position_on_new_map):

        factor = 1 / n_times_smaller

        indices_clostest = self.calculate_voronoi_diagram(int(self.width * factor), int(self.height * factor),
                                                          self.centers_x, self.centers_y)
        indices_clostest = cv2.resize(indices_clostest.astype(np.float32), (self.width, self.height),
                                      interpolation=cv2.INTER_NEAREST)
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



    def plot_px_corners(self, map_elements):
        import matplotlib.pyplot as plt
        colors = ['r', 'g', 'b', 'c', 'm', 'y', 'k', 'w']
        for i, element in enumerate(map_elements):
            px_corners = element.px_corners
            x = [px_corners[0][0], px_corners[1][0], px_corners[2][0], px_corners[3][0], px_corners[0][0]]
            y = [px_corners[0][1], px_corners[1][1], px_corners[2][1], px_corners[3][1], px_corners[0][1]]
            #draw every element in a new color
            color = colors[i % len(colors)]
            plt.plot(x, y, color)
            # also plot center
            plt.plot(element.px_center[0], element.px_center[1], color + '.')

        plt.savefig('static/debug/px_corners.png')
        plt.close()

    def plot_gps_corners(self, map_elements):
        import matplotlib.pyplot as plt
        for element in map_elements:
            gps_corners = element.gps_corners
            x = [gps_corners[0].longitude, gps_corners[1].longitude, gps_corners[2].longitude, gps_corners[3].longitude, gps_corners[0].longitude]
            y = [gps_corners[0].latitude, gps_corners[1].latitude, gps_corners[2].latitude, gps_corners[3].latitude, gps_corners[0].latitude]
            plt.plot(x, y, 'r')

        plt.savefig('static/debug/gps_corners.png')
        plt.close()

    def save_voronoi(self):
        # the closest index voronoi is a 2d array with the index of the closest map element for each pixel
        # before beeing saved its values need to be scaled between 0 and 255
        # the voronoi is saved as a png image
        voronoi = self.closest_index_voronoi
        voronoi = voronoi.astype(np.float32)
        voronoi = (voronoi - np.min(voronoi)) / (np.max(voronoi) - np.min(voronoi))
        voronoi = voronoi * 255
        voronoi = voronoi.astype(np.uint8)
        cv2.imwrite("static/debug/voronoi.png", voronoi)
