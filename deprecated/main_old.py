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
import datetime
import argparse

from src.deprecated.image_mapper import ImageMapper
from PanoramaViewer import Panorma_viewer

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

    # if len(sys.argv) < NUMBER_ARGS:
    #     print("python3 main.py path_to_images")
    #     print("Need at least" + str(NUMBER_ARGS-1) + " arguments but got " + str(len(sys.argv)-1))
    #     exit()

    parser = argparse.ArgumentParser(description='Image Mapper')

    parser.add_argument('Path', metavar='path', type=str, help='the path to the images')
    parser.add_argument('-o', '--with_odm', action='store_true', help='Use ODM to generate a seamless orthophoto')
    parser.add_argument('-p', '--odm_docker_port', type=int, default=3001 , help='the localhost port of the ODM docker container')
    parser.add_argument('-s', '--odm_resize_to', type=int, default=800 , help='the preferred size of the input images for ODM')
    parser.add_argument('--gimbal_deviation_tolerance', type=int, default=1, help='how many degrees the gimbal pitch is allowed to deviate from 90 degrees')
    parser.add_argument('--map_size', type=int, default=2500, help='size of the map in pixels')



    args = parser.parse_args()

    print('running with args:', args)

    path_to_images = args.Path
    gimbal_variance = args.gimbal_deviation_tolerance

    map_width_px= args.map_size
    map_height_px= args.map_size
    blending = 0.7   
    optimize = True
    with_odm = args.with_odm

    path = path_to_images
    if path_to_images[-1] != "/":
        path += "/"

    image_mapper = ImageMapper(path_to_images, map_width_px, map_height_px, blending, optimize, gimbal_variance, with_odm)
    panoviewer = Panorma_viewer(path)
    pano_files = panoviewer.generate_reports()
    # TODO Report muss dann die Seiten in die html einbinden
    # zusätzlich panellum in verzeichnis kopieren
    image_mapper.create_flight_report(pano_files)
        
    print("-Creating GPX file...")
    #TODO das shell script komplett durch os.system Befehle ersetzen
    os.system(": $(./get-gps-info.sh "+path+" False &)")
    os.system(": $(./get-gps-info.sh "+path+"ir/"+" False &)")
    print("-Done!")
    image_mapper.show_flight_report()
    if(with_odm):
        image_mapper.generate_odm_orthophoto(args.odm_docker_port, args.odm_resize_to)

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
