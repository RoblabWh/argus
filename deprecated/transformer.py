#!/usr/bin/env python3
__author__      = "Artur Leinweber"
__copyright__ = "Copyright 2020"
__credits__ = ["None"]
__license__ = "GPL"
__version__ = "1.0.1"
__maintainer__ = "Artur Leinweber"
__email__ = "arturleinweber@live.de"
__status__ = "Production"

import numpy as np
import math
import datetime
import cv2
import shapely

from copy import deepcopy
from rectangle import RotatedRect
from optimizer import Optimizer
from intersection_calculator import IntersectionCalculator
from intersection_calculator import IntersectionException
#from skimage import img_as_float

class Coordinate:
    def __init__(self,x,y):
        self.x = x
        self.y = y
        
class Transformer(Optimizer):
    def __init__(self, map_elements, quantity):
        super(Transformer, self).__init__()
        self.map_elements = map_elements
        self.warp_matrix = None
        #self.warp_mode = cv2.MOTION_TRANSLATION
        self.warp_mode = cv2.MOTION_EUCLIDEAN
        if self.warp_mode == cv2.MOTION_HOMOGRAPHY :
            self.warp_matrix = np.eye(3, 3, dtype=np.float32)
        else:
            self.warp_matrix = np.eye(2, 3, dtype=np.float32)

        # Specify the number of iterations.
        self.number_of_iterations = quantity;

        # Specify the threshold of the increment
        # in the correlation coefficient between two iterations
        self.termination_eps = 1e-20;

        # Define termination criteria
        self.criteria = (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, self.number_of_iterations,  self.termination_eps)         

    def optimize(self):
        for index in range(len(self.map_elements)-1):
                start = datetime.datetime.now()
                try:
                    img1, img2 = IntersectionCalculator.get_image_intersections(self.map_elements[index], self.map_elements[index+1])
                    print(img1.shape, img2.shape)
                    img1_gray = cv2.cvtColor(img1, cv2.COLOR_BGR2GRAY)
                    img2_gray = cv2.cvtColor(img2, cv2.COLOR_BGR2GRAY)
                    (cc, transformation_matrix) = cv2.findTransformECC(img1_gray, img2_gray, self.warp_matrix, self.warp_mode, self.criteria)

                    if transformation_matrix is not None or transformation_matrix is not []:
                        x_off = (transformation_matrix[0][2])
                        y_off = (transformation_matrix[1][2])


                        a = (transformation_matrix[0][0])
                        b = (transformation_matrix[0][1])


                        d = (transformation_matrix[1][0])
                        e = (transformation_matrix[1][1])
                          
                        scaling_x = math.copysign(1, a) * math.sqrt(a*a+b*b)
                        scaling_y = math.copysign(1, e) * math.sqrt(d*d+e*e)
                        
                        angle1 = math.degrees(math.atan2(-b, a))
                        angle2 = math.degrees(math.atan2(d, e))

                        #if abs(angle1) < 5 and abs(x_off) < self.spreading_range and abs(y_off) < self.spreading_range:
                        for jndex in range(index ,len(self.map_elements)-1):
                            rect2 = self.map_elements[jndex+1].get_rotated_rectangle()
                            x1, y1 = rect2.get_center()
                            rect2.set_center((x1 - int(x_off), y1 + int(y_off)))
                            rect2.set_angle(rect2.get_angle() + angle1)
                            print(int(x_off), int(y_off))
        #for i in range(len(self.map_elements)-1):
        #        print(i)
        #        try:
        #            img1, img2 = IntersectionCalculator.get_image_intersections(self.map_elements[i], self.map_elements[i+1])
        #            img1_gray = cv2.cvtColor(img1, cv2.COLOR_BGR2GRAY)
        #            img2_gray = cv2.cvtColor(img2, cv2.COLOR_BGR2GRAY)
                    
                    

        #            cx_rel, cy_rel = self.calc_relative_distance(img1) 
                    #polygon = shapely.affinity.affine_transform(rotated_rect.get_contour(),[a,b,d,e,x_off,y_off])
                    #cx, cy = polygon.centroid.coords[0]
                    #print("transformation matrix:", self.warp_matrix)
                    #print("center:", rotated_rect.get_center(), " -> ", "(",int(cx),", ",int(cy),")")
                    #print("angle:",rotated_rect.get_angle(), " -> ", rotated_rect.get_angle() + np.rad2deg(math.acos(a)))
         #           cx, cy = self.map_elements[i].get_rotated_rectangle().get_center()
         #           self.map_elements[i+1].get_rotated_rectangle().set_center((int(cx+cx_rel), int(cy+cy_rel)))
                    #rotated_rect.set_angle(rotated_rect.get_angle() + rot)  
                    
                except (IntersectionException):
                    print("IntersectionException -> pass")
        
        return self.map_elements
        

    def calc_relative_distance(self, img1):
        x_off = (self.warp_matrix[0][2])
        y_off = (self.warp_matrix[1][2])
        a = (self.warp_matrix[0][0])
        b = (self.warp_matrix[0][1])
        d = (self.warp_matrix[1][0])
        e = (self.warp_matrix[1][1])
        r1 = RotatedRect(img1.shape[1] / 2, img1.shape[0]/2, img1.shape[1], img1.shape[0], 0)
        polygon = shapely.affinity.affine_transform(r1.get_contour(),[a,b,d,e,x_off,y_off])
        cx_old, cy_old = r1.get_contour().centroid.coords[0]
        cx_new, cy_new = polygon.centroid.coords[0]
        print(cx_old, cy_old)
        print(cx_new, cy_new)
        print("Relative Translation:",cx_old-cx_new, cy_old-cy_new)
        return cx_old-cx_new, cy_old-cy_new

