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
from filter import Filter
from re import search


class PanoFilter(Filter):

    def __init__(self, keyword):
        super(PanoFilter, self).__init__()
        self.keyword = keyword
   
    def filter(self, images):
        filtered_images = list()
        for image in images:
            keyword = image.get_exif_header().get_keyword()
            
            if not search(keyword, self.keyword):
                 filtered_images.append(image)
        return filtered_images
        

