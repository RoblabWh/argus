#!/usr/bin/env python3
__author__      = "Artur Leinweber"
__copyright__ = "Copyright 2020"
__credits__ = ["None"]
__license__ = "GPL"
__version__ = "1.0.1"
__maintainer__ = "Artur Leinweber"
__email__ = "arturleinweber@live.de"
__status__ = "Production"

import sys
import math
import cv2
import numpy as np

from scipy.linalg import norm
from scipy import sum, average
from skimage.measure import compare_ssim
from PIL import ImageChops

class Comparator:

    @staticmethod
    def get_manhatten_norm(image_1, image_2):
        #print(image_1)
        #print(image_2)
        #if image_1.shape == image_2.shape and image_1 is not None and image_2 is not None and image_1 is not [] and image_2 is not [] and len(image_1) > 0 and len(image_2) > 0:
        #try:
        gray_image_1 = to_grayscale(image_1)
        gray_image_2 = to_grayscale(image_2)
        n_image_1 = normalize(gray_image_1)
        n_image_2 = normalize(gray_image_2)
        abs_diff = abs(n_image_1 - n_image_2)
        m_norm = sum(abs_diff)
        #except (ZeroDivisionError, TypeError, ValueError):
        return m_norm

    @staticmethod
    def get_zero_norm(image_1, image_2):
        n_image_1 = normalize(to_grayscale(image_1))
        n_image_2 = normalize(to_grayscale(image_2))
        diff = n_image_1 - n_image_2
        z_norm = norm(diff.ravel(), 0)

        return z_norm

#https://gist.github.com/gonzalo123/df3e43477f8627ecd1494d138eae03ae
    @staticmethod
    def mse(imageA, imageB):
        # the 'Mean Squared Error' between the two images is the
        #sum of the squared difference between the two images;
        # NOTE: the two images must have the same dimension
        err = np.sum((imageA.astype("float") - imageB.astype("float")) ** 2)
        err /= float(imageA.shape[0] * imageA.shape[1])
        return err

#https://docs.opencv.org/3.4/d8/dc8/tutorial_histogram_comparison.html
#https://docs.opencv.org/3.4/d6/dc7/group__imgproc__hist.html#ga994f53817d621e2e4228fc646342d386
    @staticmethod
    def histogram(img1, img2):

        compare_method = cv2.HISTCMP_INTERSECT

        hsv1  = cv2.cvtColor(img1, cv2.COLOR_BGR2HSV)
        hsv2  = cv2.cvtColor(img2, cv2.COLOR_BGR2HSV)
     
        h_bins = 50
        s_bins = 60
        histSize = [h_bins, s_bins]
        # hue varies from 0 to 179, saturation from 0 to 255
        h_ranges = [0, 180]
        s_ranges = [0, 256]
        ranges = h_ranges + s_ranges # concat lists
        # Use the 0-th and 1-st channels
        channels = [0, 1]

        hist1 = cv2.calcHist([hsv1], channels, None, histSize, ranges, accumulate=False)
        cv2.normalize(hist1, hist1, alpha=0, beta=1, norm_type=cv2.NORM_MINMAX)

        hist2 = cv2.calcHist([hsv1], channels, None, histSize, ranges, accumulate=False)
        cv2.normalize(hist2, hist2, alpha=0, beta=1, norm_type=cv2.NORM_MINMAX)
        
        value = cv2.compareHist(hist1, hist2, compare_method) 
        return value

    @staticmethod
    def get_ssim(image_1, image_2):
        win_size = 7
        if  image_1.shape[0] < win_size or image_1.shape[1] < win_size or image_2.shape[0] < win_size or image_2.shape[1] < win_size:
            return 0
        (score, diff) = compare_ssim(image_1, image_2, full=True, multichannel=True)
        #diff = (diff * 255).astype("uint8")
        return score        

def normalize(arr):
    rng = arr.max()-arr.min()
    if rng == 0:
        rng = 1
    amin = arr.min()
    return (arr-amin)*255/rng


def to_grayscale(arr):  
    if len(arr.shape) == 3:
        return average(arr, -1)  # average over the last axis (color channels)
    else:
        return arr

#https://stackoverflow.com/questions/189943/how-can-i-quantify-difference-between-two-images 
