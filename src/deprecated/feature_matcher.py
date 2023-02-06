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
import imutils
import sys
import matplotlib.pyplot as plt
from descartes import PolygonPatch
from scipy.special import softmax

from shapely.geometry import Polygon

from copy import deepcopy
from rectangle import RotatedRect
from optimizer import Optimizer
from intersection_calculator import IntersectionCalculator
from intersection_calculator import IntersectionException
from comparator import Comparator

class FLANNException(Exception):
    def __init__(self, error):
        super(FLANNException, self).__init__()
        self.error = error

    def print_error_message(self):
        print(self.error)


class BadFeatureCountException(Exception):
    def __init__(self, error):
        super(BadFeatureCountException, self).__init__()
        self.error = error

    def print_error_message(self):
        print(self.error)

class NoFeatureFoundsException(Exception):
    def __init__(self, error):
        super(NoFeatureFoundsException, self).__init__()
        self.error = error

    def print_error_message(self):
        print(self.error)

class Coordinate:
    def __init__(self,x,y):
        self.x = x
        self.y = y
        
class FeatureMatcher(Optimizer):
    def __init__(self, map_elements, spreading_range, angle_range, optimization_rounds_per_map_element):
        super(FeatureMatcher, self).__init__()
        self.map_elements = map_elements
        self.spreading_range = spreading_range
        self.angle_range = angle_range
        self.optimization_rounds_per_map_element = optimization_rounds_per_map_element
        self.OPTIMIZE_X = 0
        self.OPTIMIZE_Y = 0
        print(self.spreading_range/self.optimization_rounds_per_map_element)
        print(self.angle_range/self.optimization_rounds_per_map_element)         

    def optimize(self):
        for index in range(len(self.map_elements)-1):
                z = 0
                start = datetime.datetime.now()
                #while True:
                for transformation_quantity in range(0,self.optimization_rounds_per_map_element):
                    if transformation_quantity == 0: 
                        self.OPTIMIZE_X = 1
                        self.OPTIMIZE_Y = 1 
                    if transformation_quantity == 1:
                        self.OPTIMIZE_X = 1
                        self.OPTIMIZE_Y = 1                    
                    try:
                        intersection_indicies = list()
                        area_list = list()
                        for i in range(index+1):
                            has_intersection, area = IntersectionCalculator.has_intersections(self.map_elements[i], self.map_elements[index+1])  
                            #print(has_intersection, area)
                            if(has_intersection):
                                intersection_indicies.append(i)
                                area_list.append(area)

                        decomposed_values = list()
                        number_of_good_matches = list()
                        for j in intersection_indicies:
                            #print("index of has_intersection:", j)  
                            try:
                                img_scaling = FeatureMatcher.calc_scaling(self.map_elements[j],  self.map_elements[index+1])
                                img1, img2 = IntersectionCalculator.get_image_intersections(self.map_elements[j], self.map_elements[index+1], img_scaling)
                                #print("Got Intersection...")
                                #print(img1.shape, img2.shape)
                                kaze_features = FeatureMatcher.kaze_features(img1, img2)
                                matches = FeatureMatcher.bf_match(*kaze_features)
                                transformation_matrix = FeatureMatcher.get_affine_4dof(*matches)
                                #ssim = Comparator.get_ssim(img1, img2)
                            except:
                                print(sys.exc_info())
                                continue
                                                                                  
                            x_off, y_off, angle, scaling = FeatureMatcher.decompose_transformation_matrix(transformation_matrix)
                            print("x_off, y_off, angle, scaling: ", x_off/img_scaling, y_off/img_scaling, angle, scaling)
                            x_off, y_off, angle, scaling, good_matches = self.filter(x_off/img_scaling, y_off/img_scaling, angle, scaling, len(matches[0]))
                            #x_off, y_off, angle, scaling, good_matches = FeatureMatcher.filter(x_off, y_off, angle, scaling, ssim, self.spreading_range * img_scaling)
                            number_of_good_matches.append(good_matches)
                            #decomposed_values.append((x_off/img_scaling, y_off/img_scaling, angle, scaling))
                            decomposed_values.append((x_off, y_off, angle, scaling))
                        print("Calculated transformation matrix for ",len(intersection_indicies)," map elements...")
                        print("Origin map element:     ", index+1)
                        print("Map element indicies:   ", intersection_indicies)
                        print("Number of good matches: ", number_of_good_matches)
                        if len(number_of_good_matches) < 1: break
                        ssim_scores = self.choose_winner(decomposed_values, index)
                        print("SSIM scores:            ", ssim_scores) 
                        np_decomposed_values = np.asarray(decomposed_values)
                        #print(np_decomposed_values)
                        #if np.sum(np.asarray(number_of_good_matches)) != 0:
                        #    good_matches_normalized = np.asarray(number_of_good_matches)/np.sum(np.asarray(number_of_good_matches))
                        
                        #good_matches_normalized = softmax(np.asarray(number_of_good_matches))
                        good_matches_normalized = softmax(np.asarray(ssim_scores)*(np.asarray(number_of_good_matches)))
                        avg_decomposed_values = np.average(np_decomposed_values, axis= 0, weights= good_matches_normalized)
                        print("#############################")
                        print(np_decomposed_values)
                        print(good_matches_normalized)
                        print(avg_decomposed_values)
                        print("#############################")   
                        if len(avg_decomposed_values) > 0:
                            (x_off, y_off, angle, scaling) =  avg_decomposed_values
                            print("transformation values:", avg_decomposed_values)
                            if abs(x_off) <= 1 and abs(y_off) <= 1 and abs(angle) < 0.09: 
                                break 

                            print("Add transformation to other map elements...")
                            for jndex in range(index ,len(self.map_elements)-1):
                                rect2 = self.map_elements[jndex+1].get_rotated_rectangle()
                                x1, y1 = rect2.get_center()
                                rect2.set_center((x1 - int(x_off), y1 + int(y_off)))
                                rect2.set_angle(rect2.get_angle() + angle)
                                z = z + 1
                                #rect2 = self.map_elements[jndex+1].get_rotated_rectangle()
                                #w, h = rect2.get_size()
                                #new_w, new_h = int(w*scaling), int(h*scaling)
                                #rect2.set_size((new_w, new_h))
                                
                        else: break
                    except:
                        print("SOMETHING WENT WRONG!!!")
                        print("Unexpected error:", sys.exc_info()[0])
                        raise
                print("-----------------------------------------------------------------------------------------")
                print(index+1, " of ", len(self.map_elements)-1, " stichings done with ", z , " transformations ")
                print("Optimization for one map element: "+ str(int((datetime.datetime.now()-start).total_seconds())) + " [s]")
                print("-----------------------------------------------------------------------------------------")    
        return self.map_elements
    
    def choose_winner(self, decomposed_values, index):
        ssim_scores = list()
        for decomposed_value in decomposed_values:
            x_off, y_off, angle, scaling = decomposed_value 
        
            for jndex in range(index ,len(self.map_elements)-1):
                rect2 = self.map_elements[jndex+1].get_rotated_rectangle()
                x1, y1 = rect2.get_center()
                rect2.set_center((x1 - int(x_off), y1 + int(y_off)))
                rect2.set_angle(rect2.get_angle() + angle)

            area_list = list()
            intersection_indicies = list()
            for i in range(index+1):
                has_intersection, area = IntersectionCalculator.has_intersections(self.map_elements[i], self.map_elements[index+1])  
                #print(has_intersection, area)
                if(has_intersection):
                    intersection_indicies.append(i)
                    area_list.append(area)
            
            
            if len(intersection_indicies) > 0:
                area_np_array = np.asarray(area_list) / max(area_list)
                ssim_avg = 0
                i = 0
                for j in intersection_indicies:
                    try:
                        img_scaling = FeatureMatcher.calc_scaling(self.map_elements[j],  self.map_elements[index+1])
                        img1, img2 = IntersectionCalculator.get_image_intersections(self.map_elements[j], self.map_elements[index+1], img_scaling)
                        ssim = Comparator.get_ssim(img1, img2)
                        ssim_avg = ssim_avg + ssim * area_np_array[i]
                    except:
                        print(sys.exc_info())
                        continue
                    i = i + 1
            
                ssim_scores.append(ssim_avg / len(intersection_indicies))
            else:
                ssim_scores.append(0)
 
            for jndex in range(index ,len(self.map_elements)-1):
                rect2 = self.map_elements[jndex+1].get_rotated_rectangle()
                x1, y1 = rect2.get_center()
                rect2.set_center((x1 + int(x_off), y1 - int(y_off)))
                rect2.set_angle(rect2.get_angle() - angle)
        
        return ssim_scores      



    def filter(self, x_off, y_off, angle, scaling, good_matches):
        if abs(angle) > self.angle_range:# or abs(x_off) > spreading_range or abs(y_off) > spreading_range:
            angle = 0
            x_off = 0
            y_off = 0
            scaling = 0
            good_matches = 0
        
        if abs(angle) > self.angle_range/self.optimization_rounds_per_map_element:
            angle = (self.angle_range/self.optimization_rounds_per_map_element) * FeatureMatcher.get_sign(angle)
        #
        if abs(x_off) > self.spreading_range/self.optimization_rounds_per_map_element:
            x_off = self.spreading_range/self.optimization_rounds_per_map_element * FeatureMatcher.get_sign(x_off)
        #
        if abs(y_off) > self.spreading_range/self.optimization_rounds_per_map_element:
            y_off = self.spreading_range/self.optimization_rounds_per_map_element * FeatureMatcher.get_sign(y_off)
        #
        return x_off *self.OPTIMIZE_X, y_off *self.OPTIMIZE_Y, angle, scaling, good_matches 

    @staticmethod
    def get_sign(number):
        if number < 0:
            return -1
        else:
            return +1

    @staticmethod
    def calc_scaling(map_element1, map_element2):
        r1 = map_element1.get_rotated_rectangle()
        r2 = map_element2.get_rotated_rectangle()
        w_r1, h_r1 = r1.get_size()
        w_r2, h_r2 = r2.get_size()
        scaling =  min(map_element1.get_image().get_width(), map_element2.get_image().get_width())/min(w_r1, w_r2)
        return scaling

    @staticmethod
    def decompose_transformation_matrix(transformation_matrix):
        #print("transformation_matrix:\n", transformation_matrix)
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
        #print("Offset of x, y: ",-int(x_off), int(y_off))
        #print("Angle: ", angle1, angle2)
        #print("Scale: ", scaling_x,  scaling_y)
        return x_off, y_off, angle1, scaling_x        


    @staticmethod
    def kaze_features(gray1, gray2):
        # initialize the AKAZE descriptor, then detect keypoints and extract
        # local invariant descriptors from the image
        #detector = cv2.xfeatures2d.SURF_create()
        try:
            #detector = cv2.KAZE_create()
            detector = cv2.xfeatures2d.SIFT_create()
            (kps1, descs1) = detector.detectAndCompute(gray1, None)
            (kps2, descs2) = detector.detectAndCompute(gray2, None)
            #if len(kps1) > 0  and len(descs1) >0 and len(kps2)>0 and len(descs2)>0:
            #print("keypoints: {}, descriptors: {}".format(len(kps1), descs1.shape))
            #print("keypoints: {}, descriptors: {}".format(len(kps2), descs2.shape))
            return (kps1,descs1,kps2,descs2)
        except:
            raise NoFeatureFoundsException("No features were found...")
       
    @staticmethod
    def bf_match(kps1,descs1,kps2,descs2, normType = cv2.NORM_L1, crossCheck = False, distance_epsilon=0.9):
        good = []
        try:
            bf = cv2.BFMatcher(normType,crossCheck)
            matches = bf.knnMatch(descs1,descs2, k=2)    # typo fixed

            #Apply ratio test
            for m,n in matches:
                if m.distance < distance_epsilon * n.distance:
                    good.append(m)
            return (good,kps1,kps2)
        except:
            print(sys.exc_info()[0])
            raise FLANNException("Brute Force Based Matcher failed to match features...")
            #return (good,kp1,kp2)

    @staticmethod
    def flann_match(kp1,des1,kp2,des2,index_params=dict(algorithm = 1, trees = 5)):
        good = []
        try:
            #function_name = inspect.currentframe().f_code.co_name
            # FLANN parameters     
            search_params = dict(checks=50)   # or pass empty dictionary
            flann = cv2.FlannBasedMatcher(index_params,search_params)
            matches = flann.knnMatch(des1,des2,k=2)
            # Need to draw only good matches, so create a mask
            matchesMask = [[0,0] for i in range(len(matches))]
            # ratio test as per Lowe's paper
            
            for i,(m,n) in enumerate(matches):
                if m.distance < 0.7*n.distance:
                    matchesMask[i]=[1,0]
                    good.append(m)
            #draw_params = dict(matchColor = (0,255,0), singlePointColor = (255,0,0), matchesMask = matchesMask, flags = cv.DrawMatchesFlags_DEFAULT)
            #img3 = cv.drawMatchesKnn(img1,kp1,img2,kp2,matches,None,**draw_params)
            #plt.imshow(img3),plt.show()
            return (good,kp1,kp2)
        except:
            #print(sys.exc_info())
            raise FLANNException("Flann Based Matcher failed to match features...")
            #return (good,kp1,kp2)

    def get_affine_4dof(good, kp1, kp2):
        MIN_MATCH_COUNT = 4

        if len(good)>MIN_MATCH_COUNT:
            #print("Features matched...")
            src_pts = np.float32([ kp1[m.queryIdx].pt for m in good ]).reshape(-1,1,2)
            dst_pts = np.float32([ kp2[m.trainIdx].pt for m in good ]).reshape(-1,1,2)
            #M, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC,5.0)
            #M = cv2.estimateRigidTransform(src_pts, dst_pts, False)
            #matchesMask = mask.ravel().tolist()
            #h,w = img1.shape
            M, inliner = cv2.estimateAffinePartial2D(src_pts, dst_pts)
        else:
            #print("MIN_MATCH_COUNT was "+ str(MIN_MATCH_COUNT)+", but got only "+str(len(good))+" ...")
            #M = [[0,0,0],[0,0,0],[0,0,0]]
            raise BadFeatureCountException("MIN_MATCH_COUNT was "+ str(MIN_MATCH_COUNT)+", but got only "+str(len(good))+" ...")
        return M
    
