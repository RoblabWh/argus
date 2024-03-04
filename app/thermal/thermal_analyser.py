import json
import time
import cv2
import numpy as np
from thermal.thermal import Thermal
import multiprocessing



class ThermalAnalyser:
    def __init__(self, project_manager,
                 dirp_filename='thermal/plugins/dji_thermal_sdk_v1.4_20220929/tsdk-core/lib/linux/release_x64/libdirp.so',
                 dirp_sub_filename='thermal/plugins/dji_thermal_sdk_v1.4_20220929/tsdk-core/lib/linux/release_x64/libv_dirp.so',
                 iirp_filename='thermal/plugins/dji_thermal_sdk_v1.4_20220929/tsdk-core/lib/linux/release_x64/libv_iirp.so',
                 exif_filename=None, dtype=np.float32):
        self.project_manager = project_manager
        self.thermal = Thermal(
            dirp_filename=dirp_filename,
            dirp_sub_filename=dirp_sub_filename,
            iirp_filename=iirp_filename,
            exif_filename=exif_filename,
            dtype=dtype,
        )

    def get_image_temp_matrix(self, report_id, image_filename):
        try:
            temperature = self.parse_image(image_filename)
            return temperature
        except Exception as e:
            return self.approximate_temp_matrix_fast_multi(report_id, image_filename)

    def parse_image(self, image_filename):
        temperature = self.thermal.parse_dirp2(image_filename=image_filename)
        if isinstance(temperature, np.ndarray):
            return temperature
        else:
            raise Exception('Error parsing image')

    def approximate_temp_matrix_fast(self, report_id, image_filename):
        start = time.time()
        settings = self.project_manager.get_ir_settings(report_id)
        gradient_id = settings['ir_color_scheme']

        lut = json.load(open("./static/default/gradient_luts/gradient_lut_" + str(gradient_id) + ".json"))
        lut_len=len(lut)
        lut_len_divisor = 1 / lut_len
        lut_array = np.array(lut)[:, :-1]
        # print('lut_array shape: ', lut_array.shape, flush=True)

        min_temp = settings['ir_min_temp']
        max_temp = settings['ir_max_temp']
        delta_temp = max_temp - min_temp

        image = cv2.cvtColor(cv2.imread(image_filename), cv2.COLOR_BGR2RGB)
        #print('image shape: ', image.shape, flush=True)

        distances_squared = np.sum((image.reshape(image.shape[0], image.shape[1], 1, 3) -
                                    lut_array.reshape(1, 1, lut_len, 3)) ** 2, axis=-1)
        #print('distances_squared shape: ', distances_squared.shape, flush=True)

        # Find the index of the color with the smallest squared distance for each pixel
        closest_index = np.argmin(distances_squared, axis=-1)
        #print('closest_index shape: ', closest_index.shape, flush=True)

        #calculate temperature from index
        temp_matrix = min_temp + (closest_index * lut_len_divisor) * delta_temp
        #print('temp_matrix: ', temp_matrix, flush=True)

        end = time.time()
        print('approximate_temp_matrix_fast took: ', end - start, flush=True)

        return temp_matrix

    @staticmethod
    def process_row(args):
        image_row, lut_array = args
        row_distances_squared = np.sum((image_row[:, np.newaxis, :] - lut_array) ** 2, axis=-1)
        return np.argmin(row_distances_squared, axis=-1)

    def approximate_temp_matrix_fast_multi(self, report_id, image_filename):
        start = time.time()

        settings = self.project_manager.get_ir_settings(report_id)
        gradient_id = settings['ir_color_scheme']

        lut = json.load(open("./static/default/gradient_luts/gradient_lut_" + str(gradient_id) + ".json"))
        lut_len = len(lut)
        lut_len_divisor = 1 / lut_len
        lut_array = np.array(lut)[:, :-1]
        # print('lut_array shape: ', lut_array.shape, flush=True)

        min_temp = settings['ir_min_temp']
        max_temp = settings['ir_max_temp']
        delta_temp = max_temp - min_temp

        image = cv2.cvtColor(cv2.imread(image_filename), cv2.COLOR_BGR2RGB)

        num_cores = multiprocessing.cpu_count()
        pool = multiprocessing.Pool(processes=num_cores)
        rows_to_process = [(np.array(image_row), lut_array) for image_row in image]
        # luts = [self.lut_array for _ in range(len(rows_to_process))]

        closest_indices = pool.map(self.process_row, rows_to_process)
        closest_index = np.array(closest_indices)

        temp_matrix = min_temp + (closest_index * lut_len_divisor) * delta_temp

        pool.close()
        pool.join()

        end = time.time()
        print('approximate_temp_matrix_fast took:', end - start, 'seconds', flush=True)

        return temp_matrix


    def approximate_temp_matrix(self, report_id, image_filename):

        settings = self.project_manager.get_ir_settings(report_id)
        gradient_id = settings['ir_color_scheme']
        print('gradient_id: ', gradient_id, 'settings: ', settings, 'image_filename: ', image_filename, flush=True)

        lut = json.load(open("./static/default/gradient_luts/gradient_lut_" + str(gradient_id) + ".json"))
        min_temp = settings['ir_min_temp']
        max_temp = settings['ir_max_temp']

        image = cv2.imread(image_filename)
        print('image shape: ', image.shape, flush=True)

        #generate empty matrix in the shape of the image
        temp_matrix = np.zeros((image.shape[0], image.shape[1]))
        print('temp_matrix with zeros: ', temp_matrix, flush=True)

        #loop over image
        for y in range(image.shape[1]):
            print('row: ', y, flush=True)
            for x in range(image.shape[0]):
                color = image[x, y]
                index_of_closest_color = self.find_closest_color(color, lut)
                temp = self.get_temp_from_index(index_of_closest_color, min_temp, max_temp, len(lut))
                temp_matrix[x, y] = temp
        print('temp_matrix: ', temp_matrix, flush=True)
        return temp_matrix

    def find_closest_color(self, color, lut):
        closest_color = None
        closest_distance = float('inf')
        for i in range(len(lut)):
            lut_color = lut[i][:-1]
            distance = self.calculate_distance(color, lut_color)
            if distance <=0.01:
                return i
            if distance < closest_distance:
                closest_distance = distance
                closest_color = i
        return closest_color

    def calculate_distance(self, color1, color2):
        #return np.linalg.norm(color1 - color2)
        return (color1[0] - color2[0]) ** 2 + (color1[1] - color2[1]) ** 2 + (color1[2] - color2[2]) ** 2

    def get_temp_from_index(self, index, min_temp, max_temp, num_colors):
        return min_temp + (index / num_colors) * (max_temp - min_temp)
