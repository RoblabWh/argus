#!/usr/bin/env python3
__author__      = "Artur Leinweber"
__copyright__ = "Copyright 2020"
__credits__ = ["None"]
__license__ = "GPL"
__version__ = "1.0.1"
__maintainer__ = "Artur Leinweber"
__email__ = "arturleinweber@live.de"
__status__ = "Production"

from abc import ABC, abstractmethod
from .filter import Filter


class GimbalPitchFilter(Filter):

    def __init__(self, pitch_degree):
        super(GimbalPitchFilter, self).__init__()
        self.pitch_degree = pitch_degree
   
    def filter(self, images):
        filtered_images = list()
        for image in images:
            gimbal_pitch_degree = image.get_exif_header().get_xmp().get_gimbal_pitch_degree()
            if abs(gimbal_pitch_degree) > self.pitch_degree:
                 filtered_images.append(image)
        return filtered_images
            
