#!/usr/bin/env python3
__author__      = "Artur Leinweber"
__copyright__ = "Copyright 2020"
__credits__ = ["None"]
__license__ = "GPL"
__version__ = "1.0.1"
__maintainer__ = "Artur Leinweber"
__email__ = "arturleinweber@live.de"
__status__ = "Production"


import os    
import sys
import datetime

from image_mapper import ImageMapper

NUMBER_ARGS = 2

def main():   

    start = datetime.datetime.now().replace(microsecond=0)
      
    print("                                                                                               \n"+  
          "  ██╗███╗   ███╗ █████╗  ██████╗ ███████╗    ███╗   ███╗ █████╗ ██████╗ ██████╗ ███████╗██████╗\n"+ 
          "  ██║████╗ ████║██╔══██╗██╔════╝ ██╔════╝    ████╗ ████║██╔══██╗██╔══██╗██╔══██╗██╔════╝██╔══██╗\n"+
          "  ██║██╔████╔██║███████║██║  ███╗█████╗      ██╔████╔██║███████║██████╔╝██████╔╝█████╗  ██████╔╝\n"+
          "  ██║██║╚██╔╝██║██╔══██║██║   ██║██╔══╝      ██║╚██╔╝██║██╔══██║██╔═══╝ ██╔═══╝ ██╔══╝  ██╔══██╗\n"+
          "  ██║██║ ╚═╝ ██║██║  ██║╚██████╔╝███████╗    ██║ ╚═╝ ██║██║  ██║██║     ██║     ███████╗██║  ██║\n"+
          "  ╚═╝╚═╝     ╚═╝╚═╝  ╚═╝ ╚═════╝ ╚══════╝    ╚═╝     ╚═╝╚═╝  ╚═╝╚═╝     ╚═╝     ╚══════╝╚═╝  ╚═╝\n"+
          "  by Artur Leinweber, Hartmut Surmann, DRZ-Team, 2021, University of Applied Science Gelsenkirchen\n")

    if len(sys.argv) != NUMBER_ARGS:
        print("python3 main.py path_to_images")
        print("Need " + str(NUMBER_ARGS-1) + " arguments but got " + str(len(sys.argv)-1))
        exit()


    path_to_images = str(sys.argv[1])
    map_width_px= 2500
    map_height_px= 2500 
    blending = 0.7   
    optimize = True

    path = path_to_images
    if path_to_images[-1] != "/":
        path += "/"

    image_mapper = ImageMapper(path_to_images, map_width_px, map_height_px, blending, optimize)
    image_mapper.create_flight_report()
    image_mapper.show_flight_report()
    
    print("-Processing time: "+ str(datetime.datetime.now().replace(microsecond=0)-start) +" [hh:mm:ss]")
    
    print("-Creating GPX file...")
    os.system(": $(./get-gps-info.sh "+path_to_images+" &)")
    os.system(": $(./get-gps-info.sh "+path_to_images+"ir/"+" &)")
    print("-Done!")

if __name__ == "__main__":
    main()

