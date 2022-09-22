#!/usr/bin/env python3
__author__      = "Artur Leinweber"
__copyright__ = "Copyright 2020"
__credits__ = ["None"]
__license__ = "GPL"
__version__ = "1.0.1"
__maintainer__ = "Artur Leinweber"
__email__ = "arturleinweber@live.de"
__status__ = "Production"

import numpy
import cv2
import datetime
import imutils
import sys
import linecache

from PIL import Image, ImageDraw
from scipy import ndimage

from map_element import MapElement


import matplotlib.pyplot as plt
from descartes import PolygonPatch
from rectangle import RotatedRect
from shapely.geometry import Polygon
#from shapely import affinity
import shapely.affinity


class IntersectionException(Exception):
    def __init__(self, msg):
        super(IntersectionException, self).__init__()
        self.msg = msg

    def get_message(self):
        return self.msg


class IntersectionCalculator:
    @staticmethod
    def plot_intersection(r1,r2,intersection_polygon):
        fig = plt.figure("Intersection of two map elements", figsize=(10, 10))
        ax = plt.gca()
        r1_size = r1.get_size()
        r2_size = r2.get_size()
        r1_x, r1_y = r1.get_center()
        r2_x, r2_y = r2.get_center()
        map_size = max(int((r1_size[1] + r2_size[1])  + ((r1_y + r2_y)/2.0)), int((r1_size[0] + r2_size[0]) + ((r1_x + r2_x)/2.0)),)
        ax.set_xlim(0,map_size)
        ax.set_ylim(0, map_size)
        ax.add_patch(PolygonPatch(r1.get_contour(), fc='#990000', alpha=0.7))
        ax.add_patch(PolygonPatch(r2.get_contour(), fc='#000099', alpha=0.7))
        ax.add_patch(PolygonPatch(intersection_polygon, fc='#009900', alpha=1))
        plt.show()

    @staticmethod
    def get_image_intersections(map_element1, map_element2, scaling=1):
        
        #print("scaling:",scaling)
        try:
            #print("scaling:",scaling)
            r1 = map_element1.get_rotated_rectangle()
            r2 = map_element2.get_rotated_rectangle()
            #w_r1, h_r1 = r1.get_size()
            #w_r2, h_r2 = r2.get_size()
            #scaling =  min(w_r1, w_r2)/min(map_element1.get_image().get_width(), map_element2.get_image().get_width())
            r1_scaled = shapely.affinity.scale(r1.get_contour(), xfact=scaling, yfact=scaling, origin = (0,0))
            r2_scaled = shapely.affinity.scale(r2.get_contour(), xfact=scaling, yfact=scaling, origin = (0,0))

            #print(intersection_polygon)
            #if intersection_polygon.is_empty:
                #raise IntersectionException("No intersection between the two given map elements...")
            intersection_polygon = IntersectionCalculator.calculate_intersection(r1, r2)
            #IntersectionCalculator.plot_intersection(r1,r2,intersection_polygon)
            #print("intersection_polygon.exterior.coords[:]:",intersection_polygon.exterior.coords[:])
            r1_centroid = r1_scaled.centroid.coords[:]
            r2_centroid = r2_scaled.centroid.coords[:]
            cx_r1, cy_r1 = r1_centroid[0][0], r1_centroid[0][1]
            cx_r2, cy_r2 = r2_centroid[0][0], r2_centroid[0][1]
            w_r1, h_r1 = r1.get_size()
            w_r2, h_r2 = r2.get_size()
            #print("width, height: ",int(w_r1*scaling), int(h_r1*scaling), r1.get_size())
            r1_scaled = RotatedRect(cx_r1, cy_r1,int(w_r1*scaling), int(h_r1*scaling),r1.get_angle())
            r2_scaled = RotatedRect(cx_r2, cy_r2,int(w_r2*scaling), int(h_r2*scaling),r2.get_angle())
            intersection_polygon = IntersectionCalculator.calculate_intersection(r1_scaled, r2_scaled)
            #IntersectionCalculator.plot_intersection(r1_scaled, r2_scaled, intersection_polygon)
            cropped_image1 = IntersectionCalculator.crop_image(map_element1.get_image().get_matrix(), r1_scaled, intersection_polygon)
            cropped_image2 = IntersectionCalculator.crop_image(map_element2.get_image().get_matrix(), r2_scaled, intersection_polygon)
            #print("cropped_image1.shape: ", cropped_image1.shape)
            #print("cropped_image2.shape: ", cropped_image2.shape)
            if cropped_image1.shape != cropped_image2.shape:
                #print("cropped_image1.shape: ", cropped_image1.shape)
                #print("cropped_image2.shape: ", cropped_image2.shape)
                min_y = min(cropped_image1.shape[0], cropped_image2.shape[0])
                min_x = min(cropped_image1.shape[1], cropped_image2.shape[1])
                cropped_image1 =  cv2.resize(cropped_image1, (min_x, min_y), cv2.INTER_NEAREST)
                cropped_image2 =  cv2.resize(cropped_image2, (min_x, min_y), cv2.INTER_NEAREST)
            IntersectionCalculator.save_intersection_images(cropped_image1, cropped_image2)
            return (cropped_image1, cropped_image2)
        except:
            exc_type, exc_obj, tb = sys.exc_info()
            f = tb.tb_frame
            lineno = tb.tb_lineno
            filename = f.f_code.co_filename
            linecache.checkcache(filename)
            line = linecache.getline(filename, lineno, f.f_globals)
            print('EXCEPTION IN ({}, LINE {} "{}"): {}'.format(filename, lineno, line.strip(), exc_obj))
            raise IntersectionException("No intersection between the two given map elements...")
            
    @staticmethod
    def has_intersections(map_element1, map_element2):
        rotated_rect1 = map_element1.get_rotated_rectangle()
        rotated_rect2 = map_element2.get_rotated_rectangle()
        intersection_polygon = IntersectionCalculator.calculate_intersection(rotated_rect1, rotated_rect2)
        if not intersection_polygon.is_empty:
            area = intersection_polygon.area
            #print("has_intersections function:",intersection_polygon)
            return True, area
        else:
            return False, 0

    @staticmethod
    def save_intersection_images(img1, img2):
        path = "./intersections/"
        file_name1 = path + str(datetime.datetime.now())+"_1.jpg"
        file_name2 = path + str(datetime.datetime.now())+"_2.jpg"        
        cv2.imwrite(file_name1, img1)
        cv2.imwrite(file_name2, img2)
        #exit()

    @staticmethod
    def calculate_intersection(rotated_rect1, rotated_rect2):
        #rotated_rect1 = map_element1.get_rotated_rectangle()
        #rotated_rect2 = map_element2.get_rotated_rectangle()
        #print(rotated_rect1.get_shape())
        #print(rotated_rect2.get_shape())
        intersection_polygon = rotated_rect2.get_contour().intersection(rotated_rect1.get_contour())
        #print(intersection_polygon.shape)
        return intersection_polygon
        
    @staticmethod
    def crop_image(rect_image, rotated_rect, intersection_polygon):
        #cv2.imshow('image', rect_image)
        #cv2.waitKey(0)
        #cv2.destroyAllWindows()
        #intersection_polygon = affinity.scale(intersection_polygon, xfact=-1, yfact=1)
        #fig = plt.figure("Intersection of two map elements", figsize=(10, 10))
        #ax = plt.gca()
        #r1_x, r1_y = rotated_rect.get_center()
        #r1_h,r1_w = rotated_rect.get_shape()
        #ax.set_xlim(0,r1_w * 2)
        #ax.set_ylim(0, r1_h * 2)
        #ax.add_patch(PolygonPatch(intersection_polygon, fc='#009900', alpha=1))
        #ax.add_patch(PolygonPatch(rotated_rect.get_contour(), fc='#990000', alpha=0.7))
        #plt.show()




        polygon = list(map(lambda x: (int(x[0]),int(x[1])), (intersection_polygon.exterior.coords[:])))
        #print("intersection_polygon.exterior.coords[:]:", intersection_polygon.exterior.coords[:])
        yaw = rotated_rect.get_angle()
        cx, cy = rotated_rect.get_center()
        shape = rotated_rect.get_shape()
        #-------------------------------------------------------------------------------------------
        #for i in range(len(polygon)):
        #    (x,y) = polygon[i]
        #    polygon[i] = (max(0, (x-(cx-round(shape[1]/2)))),(max(0, y-(cy-round(shape[0]/2)))))
        #print("polygon:",polygon)
        #-------------------------------------------------------------------------------------------
        #+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
        (minx, miny, maxx, maxy) = rotated_rect.get_bounds()
        for i in range(len(polygon)):
            (x,y) = polygon[i]
            polygon[i] = (max(0, round(x-minx)),max(0,round(y-miny)))
        #print(polygon)
        # read image as RGB and add alpha (transparency)
        #im = Image.open(path1).convert("RGBA")
        rgba = cv2.cvtColor(rect_image, cv2.COLOR_RGB2RGBA)

        #---------------------------
        (w, h) = rotated_rect.get_size()
        rgba = cv2.resize(rgba, (w,h), cv2.INTER_NEAREST)
        #---------------------------
        #print("size",w,"x",h)

        #cv2.imshow('image_' + str(rgba.shape), rgba)
        #cv2.waitKey(0)
        #cv2.destroyAllWindows()
        # Then assign the mask to the last channel of the image
        rgba[:, :, 3] = 255
	#rotate image
        #rotated_rect_image = ndimage.rotate(rgba, yaw, reshape=True, cval= 0)
        rotated_rect_image = imutils.rotate_bound(rgba, -yaw)
        #print(-yaw)
        #cv2.imshow('rotated_rect_image_' + str(rotated_rect_image.shape) + " " + str(yaw), rotated_rect_image)
        #++++++++++++++++++++++++++++
        (h, w) = rotated_rect.get_shape()
        #print("shape",w,"x",h)
        rotated_rect_image = cv2.resize(rotated_rect_image, (round(w),round(h)), cv2.INTER_NEAREST)
        #++++++++++++++++++++++++++++
        #print(polygon)
        #cv2.imshow('rotated_rect_image_resize' + str(rotated_rect_image.shape) + " " + str(yaw), rotated_rect_image)
        #cv2.waitKey(0)
        #cv2.destroyAllWindows()
        # convert to numpy (for convenience)
        imArray = numpy.asarray(rotated_rect_image)
        #print(rotated_rect.get_shape())
        #print(imArray.shape)
        #cv2.imshow('imArray_' + str(imArray.shape), imArray)
        #cv2.waitKey(0)
        #cv2.destroyAllWindows()
        # create mask
        #polygon = [(444,203),(623,243),(691,177),(581,26),(482,42)]

        maskIm = Image.new('L', (imArray.shape[1], imArray.shape[0]), 0)
        #maskIm = Image.new('L', (imArray.shape), 0)
        ImageDraw.Draw(maskIm).polygon(polygon, outline=0, fill=255)
        mask = cv2.flip(numpy.array(maskIm.convert("RGBA")),0)
        #cv2.imshow('mask' + str(mask.shape), mask)
        # assemble new image (uint8: 0-255)
        #newImArray = numpy.empty(imArray.shape,dtype='uint8')
        #print(imArray.shape, "-", newImArray.shape)
        # colors (three first columns, RGB)
        #newImArray[:,:,:3] = imArray[:,:,:3]
        #print(imArray.shape, "-", newImArray.shape)
        # transparency (4th column)
        #newImArray[:,:,3] = mask*255
        
        #cv2.imshow('newImArray_before_min' + str(newImArray.shape), newImArray)
        x_max = max(polygon, key = lambda p: p[0])[0]
        y_max = max(polygon, key = lambda p: p[1])[1]

        x_min = min(polygon, key = lambda p: p[0])[0]
        y_min = min(polygon, key = lambda p: p[1])[1]
   
        #print(y_min,y_max,x_min,x_max)
        #print(imArray.shape, "-", mask.shape)
        newImArray = cv2.bitwise_and(imArray, mask)
        #newImArray = imArray * mask
        #cv2.imshow('newImArray_' + str(newImArray.shape), newImArray)
        #cv2.waitKey(0)
        #cv2.destroyAllWindows()
        #print(imArray.shape, "-", mask.shape, "-", newImArray.shape)
        #newImArray[:,:,3] = mask*255
        #(h, w) = (newImArray.shape[0], newImArray.shape[1])
        #newImArray = newImArray[0:h, 0:w,:]
        y_s = newImArray.shape[0] - y_max
        y_e = newImArray.shape[0] - y_min
         

        #cv2.imshow('newImArray_' + str(newImArray.shape), newImArray)

        newImArray = newImArray[y_s:y_e, x_min:x_max, : ]
        #print(imArray.shape, "-", newImArray.shape)

        #cv2.imshow('newImArray_' + str(newImArray.shape), newImArray)
        #cv2.waitKey(0)
        #cv2.destroyAllWindows()
        return newImArray
