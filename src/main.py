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
NUMBER_ARGS_OPTIONAL = 1

def main():   
    print("Sudo permission is required to add GPS based evaluations to the report")
    os.system(": $(sudo chmod +x ./get-gps-info.sh)")

    start = datetime.datetime.now().replace(microsecond=0)
      
    print("                                                                                               \n"+  
          "  ██╗███╗   ███╗ █████╗  ██████╗ ███████╗    ███╗   ███╗ █████╗ ██████╗ ██████╗ ███████╗██████╗\n"+ 
          "  ██║████╗ ████║██╔══██╗██╔════╝ ██╔════╝    ████╗ ████║██╔══██╗██╔══██╗██╔══██╗██╔════╝██╔══██╗\n"+
          "  ██║██╔████╔██║███████║██║  ███╗█████╗      ██╔████╔██║███████║██████╔╝██████╔╝█████╗  ██████╔╝\n"+
          "  ██║██║╚██╔╝██║██╔══██║██║   ██║██╔══╝      ██║╚██╔╝██║██╔══██║██╔═══╝ ██╔═══╝ ██╔══╝  ██╔══██╗\n"+
          "  ██║██║ ╚═╝ ██║██║  ██║╚██████╔╝███████╗    ██║ ╚═╝ ██║██║  ██║██║     ██║     ███████╗██║  ██║\n"+
          "  ╚═╝╚═╝     ╚═╝╚═╝  ╚═╝ ╚═════╝ ╚══════╝    ╚═╝     ╚═╝╚═╝  ╚═╝╚═╝     ╚═╝     ╚══════╝╚═╝  ╚═╝\n"+
          "  by Artur Leinweber, Hartmut Surmann, Max Schulte, Julian Klasen & DRZ-Team, 2020-2022, University of Applied Science Gelsenkirchen\n")

    if len(sys.argv) < NUMBER_ARGS:
        print("python3 main.py path_to_images")
        print("Need at least" + str(NUMBER_ARGS-1) + " arguments but got " + str(len(sys.argv)-1))
        exit()
    
    path_to_images = str(sys.argv[1])
    gimbal_variance = 0.0
    if len(sys.argv) == NUMBER_ARGS + NUMBER_ARGS_OPTIONAL:
        gimbal_variance = float(sys.argv[2])
    map_width_px= 2500
    map_height_px= 2500 
    blending = 0.7   
    optimize = True
    with_odm = True

    path = path_to_images
    if path_to_images[-1] != "/":
        path += "/"

    image_mapper = ImageMapper(path_to_images, map_width_px, map_height_px, blending, optimize, gimbal_variance)
    image_mapper.create_flight_report()
        
    print("-Creating GPX file...")
    #TODO das shell script komplett durch os.system Befehle ersetzen
    os.system(": $(./get-gps-info.sh "+path+" False &)")
    os.system(": $(./get-gps-info.sh "+path+"ir/"+" False &)")
    print("-Done!")
    image_mapper.show_flight_report()
    if(with_odm):
        image_mapper.generate_odm_orthophoto()
    print("-Processing time: "+ str(datetime.datetime.now().replace(microsecond=0)-start) +" [hh:mm:ss]")

if __name__ == "__main__":
    main()


### Changelog
# main.py: line 22 added: os.system(": $(sudo chmod +x ./get-gps-info.sh)") mit Begründungs-print davor
# camera_specs.json: komplett erneuert
# exif_header.py: read_camera_properties() umgestellt und angepasst
# html_map.py: function loadPolygons() wieder um den Pfad für die Trajectory ergänzt  ***bei beiden Report Varianten***
# html_map.py: function write_gallery() in der Schleife den Style geändert                         "style=\"display: block; max-width: 100%; max-height: 1400px; min-width: 50%; min-height: 50%; width: auto; height: auto;\"></div>"+"\n"\
# template.html: moveMagnifier() begonnen für temp zu ergänzen
# template.html: style für verlauf ergänzt
# template.html: line 130  style=\"display: inline-block; display: flex; justify-content: center;\">\
# image_mapper.py: im Konstruktor prüfen, ob am Ende des pfades ein / ist und den dann setzen
# main.py: bei dem einen os.system(": $(./get-gps-info.sh "+path+" False &)")  hinten auf false & path_to_images zu path geändert und dann den report über imagemapper.show_flight_report() angezeigt
# html_map.py: write_gallery() komplett überarbeitet
# template.html: script block von magnify komplett überarbeitet
# imgae_mapper.py: createhtml hat is_ir bekommen und übergibt das mit an die html map, wo das auch gespeichert wird
