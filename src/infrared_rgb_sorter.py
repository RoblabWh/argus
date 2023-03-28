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


def list_All_widths_with_count(images):
    widths = dict()
    for image in images:
        (width, height) = image.get_exif_header().get_image_size()
        if width in widths:
            widths[width] += 1
        else:
            widths[width] = 1

    # sort by value of keys
    widths = {k: v for k, v in sorted(widths.items(), key=lambda item: item[0], reverse=False)}
    return widths


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

        found_widths = list_All_widths_with_count(images)
        print('found_widths', found_widths)

        if len(found_widths) > 2:
            sorting_kriteria = list(found_widths.keys())[0]
        
        for image in images:
            (width, height) = image.get_exif_header().get_image_size()
            if sorting_kriteria == width: 
                images_1.append(image)
            else:
                images_2.append(image)

        if len(images_1) == 0:
            return ([], images_2)
        elif len(images_2) == 0:
            return ([], images_1)

        (width_1, height_1) = images_1[0].get_exif_header().get_image_size()
        (width_2, height_2) = images_2[0].get_exif_header().get_image_size()
        
        if width_1 < width_2:
            (infrared_images, rgb_images) = (images_1, images_2)
        else:
            (infrared_images, rgb_images) = (images_2, images_1)

        for i, infrared_image in enumerate(infrared_images):
            infrared_image.set_to_ir()

        return (infrared_images, rgb_images)

    def build_couples_path_list_from_scratch(self, images):
        couples_helper_list = list()

        (width, height) = images[0].get_exif_header().get_image_size()
        sorting_kriteria = width
        other_value = 0
        print(sorting_kriteria)

        found_widths = list_All_widths_with_count(images)
        print('found_widths', found_widths)

        if len(found_widths) > 2:
            sorting_kriteria = list(found_widths.keys())[0]

        print('sorting_kriteria', sorting_kriteria)


        for image in images:
            (width, height) = image.get_exif_header().get_image_size()
            if sorting_kriteria == width:
                couples_helper_list.append([image, True])
            else:
                couples_helper_list.append([image, False])
                other_value = width

        ir = (other_value > sorting_kriteria)

        couples_path_list = list()
        index = 0
        while index < len(couples_helper_list):
            image_path = couples_helper_list[index][0].get_image_path().split("static/")[1]

            if index + 1 < len(couples_helper_list):
                if couples_helper_list[index][1] != couples_helper_list[index + 1][1]:
                    #check id they are created within +- 1 second
                    if abs(couples_helper_list[index][0].get_exif_header().get_creation_time() - couples_helper_list[index + 1][0].get_exif_header().get_creation_time()) <= 1:
                        if(couples_helper_list[index][1] != ir):
                            couples_path_list.append([image_path, couples_helper_list[index + 1][0].get_image_path().split("static/")[1]])
                        else:
                            couples_path_list.append([couples_helper_list[index + 1][0].get_image_path().split("static/")[1], image_path])
                        index += 2
                        if(index>=len(couples_helper_list)):
                            break
                        continue

            if couples_helper_list[index][1] == ir:
                couples_path_list.append(["", image_path])
            else:
                couples_path_list.append([image_path, ""])
            index += 1

        return couples_path_list



            
