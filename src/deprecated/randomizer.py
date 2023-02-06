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

from copy import deepcopy

from optimizer import Optimizer
from intersection_calculator import IntersectionCalculator
from intersection_calculator import IntersectionException
class Coordinate:
    def __init__(self,x,y):
        self.x = x
        self.y = y
        
class Randomizer(Optimizer):
    def __init__(self, map_elements, spreading_range, quantity, distribution_function, comparator_norm):
        super(Randomizer, self).__init__()
        self.spreading_range = spreading_range
        self.quantity = quantity
        self.map_elements = map_elements
        self.comparator_norm = comparator_norm
        self.distribution_function = distribution_function

    def get_uniform(self, cartesian_coordinate):
        min_range_value = self.calculate_min_spreading(cartesian_coordinate)
        max_range_value = self.calculate_max_spreading(cartesian_coordinate)
        uniform = np.round(np.random.uniform(low=min_range_value, high=max_range_value, size=(self.quantity,2)))
        return np.concatenate((np.array([[cartesian_coordinate[0],cartesian_coordinate[1]]]), uniform), axis=0)

    def get_normal(self, cartesian_coordinate):
        normal = np.round(np.random.normal(np.array([[cartesian_coordinate[0],cartesian_coordinate[1]]]), self.spreading_range/2.0, size=(self.quantity,2)))
        return np.concatenate((np.array([[cartesian_coordinate[0],cartesian_coordinate[1]]]), normal), axis=0)        

    def calculate_min_spreading(self, cartesian_coordinate):
        x, y =cartesian_coordinate
        min_random_value_x = int(x - self.spreading_range/2.0)
        min_random_value_y = int(y - self.spreading_range/2.0)
        return (min_random_value_x, min_random_value_y)

    def calculate_max_spreading(self, cartesian_coordinate):
        x, y =cartesian_coordinate
        max_random_value_x = int(x + self.spreading_range/2.0)
        max_random_value_y = int(y + self.spreading_range/2.0)
        return (max_random_value_x, max_random_value_y)

    def optimize(self):
        for i in range(len(self.map_elements)-1):
            print("-------------------------------------------------------")
            print("Optimize: " + str(i+1) + " of " + str((len(self.map_elements)-1)))
            center_coordinate = self.map_elements[i+1].get_center_coordinate()
            #print(center_coordinate)
            distibution_coordinates = self.distribution_function(self, center_coordinate)
            #distibution_coordinates = [center_coordinate]
            #distibution_coordinates = np.asarray([center_coordinate]) 
            #print("len(distibution_coordinates):", len(distibution_coordinates))
            #print("distibution_coordinates: ", distibution_coordinates)
            comparator_scores = list()
            #start = datetime.datetime.now().replace(microsecond=0)  
            tmp_map_element = deepcopy(self.map_elements[i+1])
            #print("deepcopy: "+ str(datetime.datetime.now().replace(microsecond=0)-start)+" [hh:mm:ss]")
            j = 0
            for coordinate in distibution_coordinates:
                start = datetime.datetime.now()
                #print(j)
                tmp_map_element.get_rotated_rectangle().set_center(coordinate)
                #print("tmp_map_element.get_rotated_rectangle().set_center(coordinate)")
                try:
                    img1, img2 = IntersectionCalculator.get_image_intersections(self.map_elements[i], tmp_map_element)
                    print("Get intersection of two images: "+ str((datetime.datetime.now()-start).total_seconds() * 1000) + " [ms]")
                except (IntersectionException):
                    print("IntersectionException -> score = math.inf")
                    score = -math.inf
                else:
                    start = datetime.datetime.now()
                    score = self.comparator_norm(img1, img2)
                    print("Compare two images: "+ str((datetime.datetime.now()-start).total_seconds() * 1000) + " [ms]")

                #    print("EXCEPTION!")
                #print("img1, img2 = IntersectionCalculator.get_image_intersections(self.map_elements[i], tmp_map_element)")
                #if img1 is not None and img2 is not None:
                #else:
                
                    #print("score = self.comparator_norm(img1, img2)")
                comparator_scores.append(score)
                print("score from coord ", j, ":", score)
                j = j + 1
                
             
            score = max(comparator_scores) 
            index = comparator_scores.index(score)

            epsilon = 2.0
            rel_x = int((distibution_coordinates[index][0] - self.map_elements[i+1].get_center_coordinate()[0])/epsilon)
            rel_y = int((distibution_coordinates[index][1] - self.map_elements[i+1].get_center_coordinate()[1])/epsilon)
            self.map_elements[i+1].get_rotated_rectangle().set_center(distibution_coordinates[index])
 
            print("Add relative x, y: ",rel_x,rel_y)
            for z in range(i+2, len(self.map_elements)):
                x, y = self.map_elements[z].get_center_coordinate()
                self.map_elements[z].get_rotated_rectangle().set_center((x+rel_x,y+rel_y))

        return self.map_elements
        











    
