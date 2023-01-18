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
from sorter import Sorter
from re import search

class InfraredRGBSorter(Sorter):

    def __init__(self):
        super(InfraredRGBSorter, self).__init__()
   
    def sort(self, images):
        images_1 = list()
        images_2 = list()
        infrared_images = None
        rgb_images = None

        (width, height) = images[0].get_exif_header().get_image_size()
        sorting_kriteria = width
        
        for image in images:
            (width, height) = image.get_exif_header().get_image_size()
            if sorting_kriteria == width: 
                images_1.append(image)
            else:
                images_2.append(image)                      
        
        
        (width_1, height_1) = images_1[0].get_exif_header().get_image_size()
        (width_2, height_2) = images_2[0].get_exif_header().get_image_size()
        
        if width_1 < width_2:
            (infrared_images, rgb_images) = (images_1, images_2)
        else:
            (infrared_images, rgb_images) = (images_2, images_1)

        for i, infrared_image in enumerate(infrared_images):
            infrared_image.set_to_ir()
            infrared_image.set_rgb_counterpart_path(rgb_images[i].get_image_path())
            #TODO ungleiche Anzahl an IR/ RGB Bildern verarbeiten können
            
        return (infrared_images, rgb_images)
            
