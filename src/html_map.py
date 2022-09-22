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
from weather import Weather
from datetime import datetime, date, time
import re

class HTMLMap():
    def __init__(self, map_elements, map_height, map_width , html_file_name, map_name, area_m, altitude, processing_time, corner_gps_left_bottom, corner_gps_right_top, middle_gps, ir_path = None, ir_html_file_name=None, ir_map_name=None, is_ir=False):
        self.map_elements = map_elements
        self.map_height = map_height
        self.map_width = map_width
        self.html_file_name = html_file_name
        self.map_name = map_name
        self.area_k =  round(area_m/(1000*1000),6)
        self.avg_altitude = altitude
        self.processing_time = processing_time
        self.ir_html_file_name = ir_html_file_name
        self.ir_map_name = ir_map_name
        self.ir_path = ir_path
        self.is_only_ir = is_ir
        self.with_odm = True

        self.date = None
        self.location = None
        self.flight_time_str = None

        self.camera_model = None
        self.camera_focal_length = None
        self.camera_vertical_fov = None
        self.camera_fov = None
        self.sensor_width = None
        self.sensor_height = None
      
        self.temperature = "0"
        self.humidity = "0"
        self.altimeter = "0"
        self.wind_speed = "0"
        self.wind_dir_degrees = "0"
        self.visibility = "0"

        self.x_res = None
        self.y_res = None

        self.lat1 = corner_gps_left_bottom.get_latitude()
        self.lat2 = corner_gps_right_top.get_latitude()
        self.long1 = corner_gps_left_bottom.get_longitude()
        self.long2 = corner_gps_right_top.get_longitude()
        self.latc = middle_gps.get_latitude()
        self.longc = middle_gps.get_longitude()



        self.new_coordinates = list()

        self.extract_coordinates()
        self.get_summary()
    
    def get_summary(self):
        self.date = str(self.map_elements[0].get_image().get_exif_header().get_creation_time_str())
        try:
            self.location = str(self.map_elements[0].get_image().get_exif_header().get_gps().get_address())
        except:
            self.location = str("N/A")
            print("-Ignoring reverse adress search....")
            print("--",sys.exc_info()[0])

        flight_time_last = self.map_elements[-1].get_image().get_exif_header().get_creation_time()
        flight_time_first =  self.map_elements[0].get_image().get_exif_header().get_creation_time()
        last = time(int(flight_time_last/10000),int(flight_time_last%10000/100),int(flight_time_last%100))
        first = time(int(flight_time_first/10000),int(flight_time_first%10000/100),int(flight_time_first%100))
        flight_time = datetime.combine(date.min, last) - datetime.combine(date.min, first)

        self.flight_time_str = str(flight_time).split(":")
        self.flight_time_str = self.flight_time_str[-3] + " h : " + self.flight_time_str[-2] + " m : " + self.flight_time_str[-1] + " s"
        self.x_res = self.map_elements[0].get_image().get_width()
        self.y_res = self.map_elements[0].get_image().get_height()
        
        camera_properties = self.map_elements[0].get_image().get_exif_header().get_camera_properties()
        self.camera_model = camera_properties.get_model()
        self.camera_focal_length = camera_properties.get_focal_length()
        self.camera_fov = camera_properties.get_fov()
        self.camera_vertical_fov = camera_properties.get_vertical_fov()
        self.sensor_width, self.sensor_height = camera_properties.get_sensor_size()

        #print(self.area_k, self.avg_altitude, self.date, self.location, self.flight_time_str, self.camera_model, self.camera_fov)
        try:
            actual_weather = Weather(self.lat1, self.long1, "e9d56399575efd5b03354fa77ef54abb")
            #print(weather_info_lst)
            self.temperature = actual_weather.get_temperature()
            self.humidity = actual_weather.get_humidity()
            self.altimeter = actual_weather.get_altimeter()
            self.wind_speed = actual_weather.get_wind_speed()
            self.visibility = actual_weather.get_visibility()
            self.wind_dir_degrees = actual_weather.get_wind_dir_degrees()
        except:
            print("-Ignoring weather details...")
            print("--", sys.exc_info())
            pass

    def create_html_file(self):
        template_desciptor = open("template.html", "r")
        seperator = "<!--883458934589839458934573894573845734858345783457348534587-->"
        text = template_desciptor.read()
        splitet_template_lst = text.split(seperator)
        file_desciptor = open(str(self.html_file_name)+".html", "w")
        file_desciptor.write(splitet_template_lst[0])
        self.write_summary(file_desciptor)
        if self.ir_map_name != None and self.ir_html_file_name != None and self.ir_path != None:
            self.write_ir_map(file_desciptor)
        else:
            self.write_map(file_desciptor)
        self.write_gallery(file_desciptor)
        file_desciptor.write(splitet_template_lst[1])
        file_desciptor.close()

    def write_gallery(self, file_desciptor):
        file_desciptor.write("<div style=\"margin-top:5%\"/>\n"\
        "<div class=\"imgbox\">\n"\
        "<div id=\"i1\" class=\"container\">\n"\
        "<h2 style=\"text-align: center;margin-bottom:2%; color: white; font-size: 300%\">Images </h2>\n")

        for i in range(len(self.map_elements)):
            file_desciptor.write("<div class=\"mySlides\">\n"\
            "<div class=\"numbertext\">"+str(str(i+1)+" / "+str(len(self.map_elements)))+"</div>\n"\
            "<div id=\"slide"+str(i+1)+"\" style=\"display: inline-block; display: flex; justify-content: center;\">\n"\
            "<div class=\"img-magnifier-container\">\n")
            if self.is_only_ir:
                name_ir = str((self.map_elements[i].get_image().get_image_path().split("/"))[-1])
                name_ir = name_ir[:name_ir.rfind(".")]
                img_numbr = re.search(r'\d{0,4}$', name_ir)
                nmbr = int(img_numbr.group()) if img_numbr else None

                name_rgb = "../DJI_" + "{:>04}".format(str((nmbr-1))) + ".JPG"

                file_desciptor.write("<img class=\"overlay-img\" src=\""+ name_rgb + "\" width=\"120%\">\n")
            file_desciptor.write("<img class=\"center-mit\" id=\""+str(i+1)+"\" src=\""+str((self.map_elements[i].get_image().get_image_path().split("/"))[-1])+"\" "\
            "style=\"display: block; max-width: 100%; max-height: 1400px; min-width: 800px; width: auto; height: auto; opacity: 0.99;\"></div>"+"\n"\
            "</div>\n</div>\n")
        file_desciptor.write("<a class=\"prev\" onclick=\"plusSlides(-1)\">&#10094; </a>\n"\
        "<span id=\"temp_span\"> test </span>\n"\
        "<a class=\"next\" onclick=\"plusSlides(1)\">&#10095; </a>\n"\
        "<div class=\"caption-container\">\n"\
        "   <p id=\"caption\"/>\n"\
        "</div>\n")
        file_desciptor.write("</div>\n")

        file_desciptor.write("<div style=\"margin: auto;\" ><a><a/>\n")
        if self.is_only_ir:  # TODO die Temp-Felder mit Werten über code füllen
            file_desciptor.write("<h2 id = \"ir_temp_range\" style=\"text-align: center; color: white \">Temp Range</h2>\n" \
                                 "<div style=\"max-width: 400px; margin: auto\">\n" \
                                 "  <table cellpadding=\"4\" cellspacing=\"0\"  style=\"width: 100%; color: white \">\n" \
                                 "    <tr>\n" \
                                 "      <th>Temp.range start</th>\n" \
                                 "      <th>Temp.range end</th>\n" \
                                 "    </tr>\n" \
                                 "    <tr style=\"text-align: center\">\n" \
                                 "      <td><input type=\"number\" id=\"minTemp\" name=\"minTemp\" min=\"-20\" max=\"800\" value=\"20\" style=\"max-width: 80px\"></td>\n" \
                                 "      <td><input type=\"number\" id=\"maxTemp\" name=\"maxTemp\" min=\"-20\" max=\"800\" value=\"80\" style=\"max-width: 80px\"></td>\n" \
                                 "    </tr>\n" \
                                 "  </table>\n" \
                                 "<div id=\"grad1\"> </div>\n" \
                                 "</div>\n")
        file_desciptor.write("<div class=\"slidecontainer\">\n"\
        "<a class=\"slidetext\">&#8722; </a><div style=\"padding-top:5px;\"><input type=\"range\" min=\"2\" max=\"22\" value=\"11\" class=\"slider\" id=\"slider_range_zoom\"></div><a class=\"slidetext\"> &#43;</a>\n"\
        "</div>\n"\
        "</div>")

        
        file_desciptor.write("<div class=\"row\">\n")
    
        for i in range(len(self.map_elements)):
            file_desciptor.write("<div class=\"column\">"\
            "<img class=\"demo cursor\" src=\""+str((self.map_elements[i].get_image().get_image_path().split("/"))[-1])+"\""\
            "style=\"width:100%;\" onclick=\"currentSlide("+str(i+1)+")\""\
            "alt=\""+str((self.map_elements[i].get_image().get_image_path().split("/"))[-1])+"\">\n"\
            "</div>")
        file_desciptor.write("</div>")
        

    def write_map_old(self, file_desciptor):
        file_desciptor.write(
            "<h2 style=\"text-align: center;margin-top:5%; color: white; font-size: 300%;padding-bottom:30px;\">Map</h2>\n" \
            "<div id=\"secondMap\">\n" \
            "<svg version=\"1.1\" id=\"Layer_1\" xmlns=\"http://www.w3.org/2000/svg\" xmlns:xlink=\"http://www.w3.org/1999/xlink\" width=\"100%\" height=\"100%\"\n" \
            "viewBox=\"0 0 " + str(self.map_width) + " " + str(
                self.map_height) + "\" style=\"enable-background:new 0 0 " + str(self.map_width) + " " + str(
                self.map_height) + ";\" xml:space=\"preserve\">\n" \
                                   "<svg id=\"gMap\" class=\"center-fit\" width=\"100%\" height=\"100%\" viewBox=\"0 0 658 423\">\n" \
                                   "<image xlink:href=\"googleMapsMapPlaceholder.png\"/>\n" \
                                   "</svg>\n" \
                                   "<svg id=\"overviewMap\" class=\"center-fit\" width=\"100%\" height=\"100%\" viewBox=\"0 0 " + str(
                self.map_width) + " " + str(self.map_height) + "\">\n")

        file_desciptor.write("<image xlink:href=\"" + str(self.map_name) + "\"/>\n")

        for i in range(len(self.map_elements)):
            file_desciptor.write("<a onclick=\"currentSlide(" + str(i + 1) + ")\">\n")
            file_desciptor.write("<polyline points=\"" + str(
                self.new_coordinates[i]) + "\" fill=\"hsla(0,0%,100%,0.0)\"/>" + "\n" + "</a>")
        file_desciptor.write("</svg>\n</svg>\n</div>")

        file_desciptor.write("<div id=\"map\"></div>\n" \
                             "<div style=\"margin: auto;\" ><a><a/>\n" \
                             "<div class=\"slidecontainer\">\n" \
                             "<a class=\"slidetext\">&#8722; </a><div style=\"padding-top:5px;\"><input type=\"range\" min=\"0\" max=\"100\" value=\"100\" class=\"slider\" id=\"imageAlpha\" oninput=\"changeAlpha(this.value)\"></div><a class=\"slidetext\"> &#43;</a>\n" \
                             "</div></div>\n" \
                             "\n" \
                             "<script>\n" \
                             "var defaultZoom = 18;\n" \
                             "var map = L.map(\'map\').setView([" + str(self.latc) + "," + str(
            self.longc) + "], defaultZoom);\n" \
                          "var center = [" + str(self.latc) + "," + str(self.longc) + "];\n" \
                                                                                      "L.tileLayer(\'https://api.mapbox.com/styles/v1/{id}/tiles/{z}/{x}/{y}?access_token={accessToken}\',\n" \
                                                                                      "{\n" \
                                                                                      "attribution: \'\',\n" \
                                                                                      "maxZoom: 25,\n" \
                                                                                      "id: \'mapbox/satellite-v9\',\n" \
                                                                                      "tileSize: 512,\n" \
                                                                                      "zoomOffset: -1,\n" \
                                                                                      "accessToken: \'pk.eyJ1Ijoicm9ibGFidXNlcndocyIsImEiOiJja3VjaXF3d2MxMTN5Mm9tdmQzaGphdGU3In0.BhKF_054bVOPcviIq2yIKg\'\n" \
                                                                                      "}\n" \
                                                                                      ").addTo(map);\n" \
                                                                                      "\n" \
                                                                                      "var mapSize=[" + str(
            self.map_width) + "," + str(self.map_height) + "];\n" \
                                                           "//guessed values\n" \
                                                           "var lat1 = " + str(self.lat1) + "; // adjustable\n" \
                                                                                            "var long1 = " + str(
            self.long1) + ";\n" \
                          "var lat2 = " + str(self.lat2) + ";\n" \
                                                           "var long2 = " + str(self.long2) + ";\n" \
                                                                                              "var	imageBounds = [[lat1,long1], [lat2,long2]];//update with gps data\n" \
                                                                                              "var svg = document.getElementById(\'mymap\');\n" \
                                                                                              "var mapOverlay = L.imageOverlay(\'" + str(
            self.map_name) + "\', imageBounds);\n" \
                             "mapOverlay.addTo(map);\n" \
                             "loadPolygons();\n" \
                             "var mapOverlayOpacity = 1;\n" \
                             "\n" \
                             "function style(feature) {\n" \
                             "	return {\n" \
                             "		opacity: 0,\n" \
                             "		fillOpacity: 0,\n" \
                             "		fill: blue\n" \
                             "	}\n" \
                             "}\n" \
                             "\n" \
                             "var threshhold = 0.55;\n" \
                             "\n" \
                             "function highlightFeature(e) {\n" \
                             "	var layer = e.target;\n" \
                             "	\n" \
                             "	if(mapOverlayOpacity > threshhold) {\n" \
                             "		layer.setStyle({\n" \
                             "			fillOpacity: 0.7\n" \
                             "		});\n" \
                             "	}\n" \
                             "}\n" \
                             "\n" \
                             "function resetHighlight(e) {\n" \
                             "	var layer = e.target;\n" \
                             "	\n" \
                             "	layer.setStyle({\n" \
                             "		fillOpacity: 0\n" \
                             "	});\n" \
                             "}\n" \
                             "\n" \
                             "var polygons;\n" \
                             "function loadPolygons() {\n" \
                             "	polygons = new Array();\n" \
                             "  var centers = new Array();\n" \
                             "	var svg = document.getElementById(\'overviewMap\').getElementsByTagName(\'polyline\');\n" \
                             "	for (var i = 0; i < svg.length; i++) {\n" \
                             "		for (var j = 0; j < svg[i][\'points\'].length; j++) {			\n" \
                             "		}\n" \
                             "		//var names really bad, myb adjust\n" \
                             "		var p1=[svg[i][\'points\'][0][\'x\']/mapSize[0],svg[i][\'points\'][0][\'y\']/mapSize[1]];\n" \
                             "		var p2=[svg[i][\'points\'][1][\'x\']/mapSize[0],svg[i][\'points\'][1][\'y\']/mapSize[1]];\n" \
                             "		var p3=[svg[i][\'points\'][2][\'x\']/mapSize[0],svg[i][\'points\'][2][\'y\']/mapSize[1]];\n" \
                             "		var p4=[svg[i][\'points\'][3][\'x\']/mapSize[0],svg[i][\'points\'][3][\'y\']/mapSize[1]];\n" \
                             "		var pL1 = [p1[1] * lat1 + ((1 - p1[1]) * lat2),p1[0] * long2 + ((1 - p1[0]) * long1)];\n" \
                             "		var pL2 = [p2[1] * lat1 + ((1 - p2[1]) * lat2),p2[0] * long2 + ((1 - p2[0]) * long1)];\n" \
                             "		var pL3 = [p3[1] * lat1 + ((1 - p3[1]) * lat2),p3[0] * long2 + ((1 - p3[0]) * long1)];\n" \
                             "		var pL4 = [p4[1] * lat1 + ((1 - p4[1]) * lat2),p4[0] * long2 + ((1 - p4[0]) * long1)];\n" \
                             "		var latlngs = [pL1,pL2,pL3,pL4];\n" \
                             "      var center = [((pL1[0] + pL3[0]) / 2.0), ((pL1[1] + pL3[1]) / 2.0)];\n" \
                             "      centers.push(center);\n" \
                             "		var polygon = L.polygon(latlngs ,{ opacity: 0, fillOpacity: 0 }).addTo(map);\n" \
                             "		polygon.on(\'mouseover\', highlightFeature);\n" \
                             "		polygon.on(\'mouseout\', resetHighlight);\n" \
                             "		polygon.on(\'click\',	slide);\n" \
                             "		polygons.push(polygon);\n" \
                             "	}\n" \
                             "  trajectory = L.polyline(centers);\n" \
                             "  var overlay = {\n" \
                             "  'Gpx': trajectory\n" \
                             "  };\n" \
                             "  var gpxLayer = L.control.layers(null, overlay, {\n" \
                             "  collapsed: false,\n" \
                             "  position: 'topleft'\n" \
                             "  });\n" \
                             "  gpxLayer.addTo(map);\n" \
                             "	document.getElementById(\'secondMap\').remove();\n" \
                             "}\n" \
                             "\n" \
                             "function slide(e) {\n" \
                             "	var i = polygons.indexOf(e.target);\n" \
                             "	currentSlide(i+1);\n" \
                             "}\n" \
                             "\n" \
                             "function changeAlpha(value) {\n" \
                             "	mapOverlay.setOpacity(value/100);\n" \
                             "	mapOverlayOpacity = value/100;\n" \
                             "}\n" \
                             "<!-- home button functionality -->\n" \
                             "L.Control.zoomHome = L.Control.extend({\n" \
                             "options: {\n" \
                             "position: \'topleft\',\n" \
                             "zoomHomeText: \'&#9873;\',\n" \
                             "zoomHomeTitle: \'Zoom home\'\n" \
                             "},\n" \
                             "onAdd: function (map) {\n" \
                             "var controlName = \'gin-control-zoom\',\n" \
                             "container = L.DomUtil.create(\'div\', controlName + \' leaflet-bar\'),\n" \
                             "options = this.options;\n" \
                             "//container.innerHTML\n" \
                             "this._zoomHomeButton = this._createButton(options.zoomHomeText, options.zoomHomeTitle,\n" \
                             "controlName + \'-home\', container, this._zoomHome);\n" \
                             "return container;\n" \
                             "},\n" \
                             "onRemove: function (map) {\n" \
                             "},\n" \
                             "_zoomHome: function (e) {\n" \
                             "map.flyTo(center, defaultZoom);\n" \
                             "},\n" \
                             "_createButton: function (html, title, className, container, fn) {\n" \
                             "var link = L.DomUtil.create(\'a\', className, container);\n" \
                             "link.innerHTML = html;\n" \
                             "link.href = \'#\';\n" \
                             "link.title = title;\n" \
                             "link.role = \"button\";\n" \
                             "L.DomEvent\n" \
                             ".on(link, \'click\', fn, this)\n" \
                             ".on(link, \'click\', L.DomEvent.stop)\n" \
                             ".on(link, \'click\', this._refocusOnMap, this);;\n" \
                             "return link;\n" \
                             "},\n" \
                             "});\n" \
                             "var zoomHome = new L.Control.zoomHome();\n" \
                             "zoomHome.addTo(map);\n" \
                             "<!-- home button functionality -->\n" \
                             "</script>\n" \
                             "\n" \
                             "<script>\n" \
                             "function changeAlpha2(value) {\n" \
                             "	var map = document.getElementById(\"overviewMap\");\n" \
                             "	map.setAttribute(\"opacity\", value/100);\n" \
                             "}\n" \
                             "</script>")

    def write_ir_map(self, file_desciptor):
        file_desciptor.write("<h2 style=\"text-align: center;margin-top:5%; color: white; font-size: 300%;padding-bottom:30px;\">Map</h2>\n"\
                             "<div id=\"secondMap\">\n"\
                             "<svg version=\"1.1\" id=\"Layer_1\" xmlns=\"http://www.w3.org/2000/svg\" xmlns:xlink=\"http://www.w3.org/1999/xlink\" width=\"100%\" height=\"100%\"\n"\
	                     "viewBox=\"0 0 "+str(self.map_width)+" "+str(self.map_height)+"\" style=\"enable-background:new 0 0 "+str(self.map_width)+" "+str(self.map_height)+";\" xml:space=\"preserve\">\n"\
                             "<svg id=\"gMap\" class=\"center-fit\" width=\"100%\" height=\"100%\" viewBox=\"0 0 658 423\">\n"\
                             "<image xlink:href=\"googleMapsMapPlaceholder.png\"/>\n"\
                             "</svg>\n"\
                             "<svg id=\"overviewMap\" class=\"center-fit\" width=\"100%\" height=\"100%\" viewBox=\"0 0 "+str(self.map_width)+" "+str(self.map_height)+"\">\n")

        file_desciptor.write("<image xlink:href=\""+str(self.map_name)+"\"/>\n")
        
        for i in range(len(self.map_elements)):
            file_desciptor.write("<a onclick=\"currentSlide("+str(i+1)+")\">\n")
            file_desciptor.write("<polyline points=\""+str(self.new_coordinates[i])+"\" fill=\"hsla(0,0%,100%,0.0)\"/>"+"\n"+"</a>")
        file_desciptor.write("</svg>\n</svg>\n</div>")

        file_desciptor.write("<div id=\"map\"></div>\n"\
                             "<div style=\"margin: auto;\" ><a><a/>\n"\
                             "<div class=\"slidecontainer\">\n"\
                             "<a class=\"slidetext\">&#8722; </a><div style=\"padding-top:5px;\"><input type=\"range\" min=\"0\" max=\"100\" value=\"100\" class=\"slider\" id=\"imageAlpha\" oninput=\"changeAlpha(this.value)\"></div><a class=\"slidetext\"> &#43;</a>\n"\
                             "</div></div>\n"\
                             "\n"\
                             "<script>\n"\
                             "var defaultZoom = 18;\n"\
	                     "var map = L.map(\'map\').setView(["+str(self.latc)+","+str(self.longc)+"], defaultZoom);\n"\
	                     "var center = ["+str(self.latc)+","+str(self.longc)+"];\n"\
	                     "L.tileLayer(\'https://api.mapbox.com/styles/v1/{id}/tiles/{z}/{x}/{y}?access_token={accessToken}\',\n"\
	                     "{\n"\
	                     "attribution: \'\',\n"\
	                     "maxZoom: 25,\n"\
	                     "id: \'mapbox/satellite-v9\',\n"\
	                     "tileSize: 512,\n"\
	                     "zoomOffset: -1,\n"\
	                     "accessToken: \'pk.eyJ1Ijoicm9ibGFidXNlcndocyIsImEiOiJja3VjaXF3d2MxMTN5Mm9tdmQzaGphdGU3In0.BhKF_054bVOPcviIq2yIKg\'\n"\
	                     "}\n"\
	                     ").addTo(map);\n"\
	                     "\n"\
	                     "var mapSize=["+str(self.map_width)+","+str(self.map_height)+"];\n"\
	                     "//guessed values\n"\
	                     "var lat1 = "+str(self.lat1)+"; // adjustable\n"\
	                     "var long1 = "+str(self.long1)+";\n"\
	                     "var lat2 = "+str(self.lat2)+";\n"\
	                     "var long2 = "+str(self.long2)+";\n"\
	                     "var	imageBounds = [[lat1,long1], [lat2,long2]];//update with gps data\n"\
	                     "var svg = document.getElementById(\'mymap\');\n"\
	                     #"var mapOverlay = L.imageOverlay(\'"+str(self.map_name)+"\', imageBounds);\n"\
                             "var mapImage = L.imageOverlay(\'"+str(self.map_name)+"\', imageBounds);\n"\
                             "var mapOverlay = L.layerGroup([mapImage]);\n"\
                             "loadPolygons();\n"\
                             "\n"\
                             "var IR = L.imageOverlay(\'"+str(self.ir_path)+str(self.ir_map_name)+"\', imageBounds, {interactive: true});\n"\
                             "var inMeasureMode = false;\n"\
                             "var irOverlay = L.layerGroup([IR]);\n"\
                             "var mapOverlayOpacity = 1;\n"\
                             "IR.on(\'click\', function(e) {\n"\
                             "if(!inMeasureMode) {\n"\
                             "var loc = window.location.pathname;\n"\
                             "var url = loc.substring(0, loc.lastIndexOf(\'/\')) + \'/"+str(self.ir_path)+str(self.ir_html_file_name)+"\';\n"\
                             "window.open(url,\'_blank\');\n"\
                             "}\n"\
                             "});\n"\
                             "var threshold = 0.55;\n"\
                             "\n")

        if(self.with_odm):
            file_desciptor.write("\r\nvar ODM = L.imageOverlay(\'placeholder_map.png\', imageBounds, {interactive: true});\r\nvar odmOverlay = L.layerGroup([ODM]);\r\n\r\nfunction setODMLayerImage(path){\r\n   ODM.setUrl(path);\r\n}\r\n\r\nfunction checkImage(imageSrc, good, bad) {\r\n    var img = new Image();\r\n    img.onload = good; \r\n    img.onerror = bad;\r\n    img.src = imageSrc;\r\n}\r\n\r\ncheckImage(\'map_odm_orthophoto.png\', function(){setODMLayerImage(\'map_odm_orthophoto.png\')}, function(){setODMLayerImage(\'placeholder_map.png\')});\r\n\r\nODM.on(\'click\', function(e) {\r\n   checkImage(\'map_odm_orthophoto.png\', function(){setODMLayerImage(\'map_odm_orthophoto.png\')}, function(){setODMLayerImage(\'placeholder_map.png\')});\r\n\r\n});")

        file_desciptor.write("function highlightFeature(e) {\n"\
                             "	if(!inMeasureMode) {\n"\
                             "	if(mapOverlayOpacity > threshold) {\n"\
                             "		var layer = e.target;\n"\
                             "		layer.setStyle({\n"\
                             "			fillOpacity: 0.7\n"\
                             "		});\n"\
                             "	}\n"\
                             "	}\n"\
                             "}\n"\
                             "\n"\
                             "function resetHighlight(e) {\n"\
                             "	var layer = e.target;\n"\
                             "	\n"\
                             "	layer.setStyle({\n"\
                             "		fillOpacity: 0\n"\
                             "	});\n"\
                             "}\n"\
                             "\n"\
                             "var polygons;\n"\
                             "function loadPolygons() {\n"\
                             "	polygons = new Array();\n"\
                             "  var centers = new Array();\n"\
                             "	var svg = document.getElementById(\'overviewMap\').getElementsByTagName(\'polyline\');\n"\
                             "	for (var i = 0; i < svg.length; i++) {\n"\
                             "		for (var j = 0; j < svg[i][\'points\'].length; j++) {			\n"\
                             "		}\n"\
                             "		//var names really bad, myb adjust\n"\
                             "		var p1=[svg[i][\'points\'][0][\'x\']/mapSize[0],svg[i][\'points\'][0][\'y\']/mapSize[1]];\n"\
                             "		var p2=[svg[i][\'points\'][1][\'x\']/mapSize[0],svg[i][\'points\'][1][\'y\']/mapSize[1]];\n"\
                             "		var p3=[svg[i][\'points\'][2][\'x\']/mapSize[0],svg[i][\'points\'][2][\'y\']/mapSize[1]];\n"\
                             "		var p4=[svg[i][\'points\'][3][\'x\']/mapSize[0],svg[i][\'points\'][3][\'y\']/mapSize[1]];\n"\
                             "		var pL1 = [p1[1] * lat1 + ((1 - p1[1]) * lat2),p1[0] * long2 + ((1 - p1[0]) * long1)];\n"\
                             "		var pL2 = [p2[1] * lat1 + ((1 - p2[1]) * lat2),p2[0] * long2 + ((1 - p2[0]) * long1)];\n"\
                             "		var pL3 = [p3[1] * lat1 + ((1 - p3[1]) * lat2),p3[0] * long2 + ((1 - p3[0]) * long1)];\n"\
                             "		var pL4 = [p4[1] * lat1 + ((1 - p4[1]) * lat2),p4[0] * long2 + ((1 - p4[0]) * long1)];\n"\
                             "		var latlngs = [pL1,pL2,pL3,pL4];\n"\
                             "      var center = [((pL1[0] + pL3[0]) / 2.0), ((pL1[1] + pL3[1]) / 2.0)];\n"\
                             "      centers.push(center);\n"\
                             "		var polygon = L.polygon(latlngs ,{ opacity: 0, fillOpacity: 0, fillColor: '#0000FF' });\n"\
                             "		polygon.on(\'mouseover\', highlightFeature);\n"\
                             "		polygon.on(\'mouseout\', resetHighlight);\n"\
                             "		polygon.on(\'click\',	slide);\n"\
                             "           mapOverlay.addLayer(polygon);\n"\
                             "		polygons.push(polygon);\n"\
                             "	}\n"\
                             "  trajectory = L.polyline(centers);\n"\
                             "  var overlay = {\n"\
  	                         "  'Gpx': trajectory\n"\
                             "  };\n"\
                             "  var gpxLayer = L.control.layers(null, overlay, {\n"\
                             "  collapsed: false,\n"\
                             "  position: 'topleft'\n"\
                             "  });\n"\
                             "  gpxLayer.addTo(map);\n"\
                             "  document.getElementById(\'secondMap\').remove();\n"\
                             "}\n"\
                             "\n"\
                             "function slide(e) {\n"\
                             "	var i = polygons.indexOf(e.target);\n"\
                             "	currentSlide(i+1);\n"\
                             "}\n"\
                             "\n"\
                             "function changeAlpha(value) {\n"\
                             "    mapImage.setOpacity(value/100);\n"\
                             "    IR.setOpacity(value/100);\n")

        if(self.with_odm):
            file_desciptor.write("    ODM.setOpacity(value/100);\n")

        file_desciptor.write("    mapOverlayOpacity = value/100;\n"\
                             "}\n"\
                             "<!-- home button functionality -->\n"\
                             "L.Control.zoomHome = L.Control.extend({\n"\
                             "options: {\n"\
                             "position: \'topleft\',\n"\
                             "zoomHomeText: \'&#9873;\',\n"\
                             "zoomHomeTitle: \'Zoom home\'\n"\
                             "},\n"\
                             "onAdd: function (map) {\n"\
                             "var controlName = \'gin-control-zoom\',\n"\
                             "container = L.DomUtil.create(\'div\', controlName + \' leaflet-bar\'),\n"\
                             "options = this.options;\n"\
                             "//container.innerHTML\n"\
                             "this._zoomHomeButton = this._createButton(options.zoomHomeText, options.zoomHomeTitle,\n"\
                             "controlName + \'-home\', container, this._zoomHome);\n"\
                             "return container;\n"\
                             "},\n"\
                             "onRemove: function (map) {\n"\
                             "},\n"\
                             "_zoomHome: function (e) {\n"\
                             "map.flyTo(center, defaultZoom);\n"\
                             "},\n"\
                             "_createButton: function (html, title, className, container, fn) {\n"\
                             "var link = L.DomUtil.create(\'a\', className, container);\n"\
                             "link.innerHTML = html;\n"\
                             "link.href = \'#\';\n"\
                             "link.title = title;\n"\
                             "link.role = \"button\";\n"\
                             "L.DomEvent\n"\
                             ".on(link, \'click\', fn, this)\n"\
                             ".on(link, \'click\', L.DomEvent.stop)\n"\
                             ".on(link, \'click\', this._refocusOnMap, this);;\n"\
                             "return link;\n"\
                             "},\n"\
                             "});\n"\
                             "var zoomHome = new L.Control.zoomHome();\n"\
                             "zoomHome.addTo(map);\n"\
                             "<!-- home button functionality -->\n"\
                             "var layerswitcher = {\n"\
                             "RGB: mapOverlay,\n"\
                             "IR : irOverlay")

        if(self.with_odm):
            file_desciptor.write(",\nODM: odmOverlay\n")

        file_desciptor.write("};\n"\
                             "L.control.layers(layerswitcher,{}, {collapsed: false}).addTo(map);\n"\
                             "layerswitcher.RGB.addTo(map);\n"\
                             "</script>\n"\
                             "\n"\
                             "<script>\n"\
                             "function changeAlpha2(value) {\n"\
                             "	var map = document.getElementById(\"overviewMap\");\n"\
                             "	map.setAttribute(\"opacity\", value/100);\n"\
                             "}\n"\
                             "</script>")

    def write_map(self, file_desciptor):
        print("lat1", self.lat1, "long1", self.long1)
        print("lat2", self.lat2, "long2", self.long2)
        file_desciptor.write(
            "<h2 style=\"text-align: center;margin-top:5%; color: white; font-size: 300%;padding-bottom:30px;\">Map</h2>\n" \
            "<div id=\"secondMap\">\n" \
            "<svg version=\"1.1\" id=\"Layer_1\" xmlns=\"http://www.w3.org/2000/svg\" xmlns:xlink=\"http://www.w3.org/1999/xlink\" width=\"100%\" height=\"100%\"\n" \
            "viewBox=\"0 0 " + str(self.map_width) + " " + str(
                self.map_height) + "\" style=\"enable-background:new 0 0 " + str(self.map_width) + " " + str(
                self.map_height) + ";\" xml:space=\"preserve\">\n" \
                                   "<svg id=\"gMap\" class=\"center-fit\" width=\"100%\" height=\"100%\" viewBox=\"0 0 658 423\">\n" \
                                   "<image xlink:href=\"googleMapsMapPlaceholder.png\"/>\n" \
                                   "</svg>\n" \
                                   "<svg id=\"overviewMap\" class=\"center-fit\" width=\"100%\" height=\"100%\" viewBox=\"0 0 " + str(
                self.map_width) + " " + str(self.map_height) + "\">\n")

        file_desciptor.write("<image xlink:href=\"" + str(self.map_name) + "\"/>\n")

        for i in range(len(self.map_elements)):
            file_desciptor.write("<a onclick=\"currentSlide(" + str(i + 1) + ")\">\n")
            file_desciptor.write("<polyline points=\"" + str(
                self.new_coordinates[i]) + "\" fill=\"hsla(0,0%,100%,0.0)\"/>" + "\n" + "</a>")
        file_desciptor.write("</svg>\n</svg>\n</div>")

        file_desciptor.write("<div id=\"map\"></div>\n" \
                             "<div style=\"margin: auto;\" ><a><a/>\n" \
                             "<div class=\"slidecontainer\">\n" \
                             "<a class=\"slidetext\">&#8722; </a><div style=\"padding-top:5px;\"><input type=\"range\" min=\"0\" max=\"100\" value=\"100\" class=\"slider\" id=\"imageAlpha\" oninput=\"changeAlpha(this.value)\"></div><a class=\"slidetext\"> &#43;</a>\n" \
                             "</div></div>\n" \
                             "\n" \
                             "<script>\n" \
                             "var defaultZoom = 18;\n" \
                             "var map = L.map(\'map\').setView([" + str(self.latc) + "," + str(
            self.longc) + "], defaultZoom);\n" \
                          "var center = [" + str(self.latc) + "," + str(self.longc) + "];\n" \
                                                                                      "L.tileLayer(\'https://api.mapbox.com/styles/v1/{id}/tiles/{z}/{x}/{y}?access_token={accessToken}\',\n" \
                                                                                      "{\n" \
                                                                                      "attribution: \'\',\n" \
                                                                                      "maxZoom: 25,\n" \
                                                                                      "id: \'mapbox/satellite-v9\',\n" \
                                                                                      "tileSize: 512,\n" \
                                                                                      "zoomOffset: -1,\n" \
                                                                                      "accessToken: \'pk.eyJ1Ijoicm9ibGFidXNlcndocyIsImEiOiJja3VjaXF3d2MxMTN5Mm9tdmQzaGphdGU3In0.BhKF_054bVOPcviIq2yIKg\'\n" \
                                                                                      "}\n" \
                                                                                      ").addTo(map);\n" \
                                                                                      "\n" \
                                                                                      "var mapSize=[" + str(
            self.map_width) + "," + str(self.map_height) + "];\n" \
                                                           "//guessed values\n" \
                                                           "var lat1 = " + str(self.lat1) + "; // adjustable\n" \
                                                                                            "var long1 = " + str(
            self.long1) + ";\n" \
                          "var lat2 = " + str(self.lat2) + ";\n" \
                                                           "var long2 = " + str(self.long2) + ";\n" \
                                                                                              "var	imageBounds = [[lat1,long1], [lat2,long2]];//update with gps data\n" \
                                                                                              "var svg = document.getElementById(\'mymap\');\n" \
                                 # "var mapOverlay = L.imageOverlay(\'"+str(self.map_name)+"\', imageBounds);\n"\
                                                                                              "var mapImage = L.imageOverlay(\'" + str(
            self.map_name) + "\', imageBounds);\n" \
                             "var mapOverlay = L.layerGroup([mapImage]);\n" \
                             "loadPolygons();\n" \
                             "var mapOverlayOpacity = 1;\n"\
                             "var inMeasureMode = false\n" \
                             "\n" \
                             "var threshold = 0.55;\n" \
                             "\n")

        if (self.with_odm):
            file_desciptor.write(
                "\r\nvar ODM = L.imageOverlay(\'placeholder_map.png\', imageBounds, {interactive: true});\r\nvar odmOverlay = L.layerGroup([ODM]);\r\n\r\nfunction setODMLayerImage(path){\r\n   ODM.setUrl(path);\r\n}\r\n\r\nfunction checkImage(imageSrc, good, bad) {\r\n    var img = new Image();\r\n    img.onload = good; \r\n    img.onerror = bad;\r\n    img.src = imageSrc;\r\n}\r\n\r\ncheckImage(\'map_odm_orthophoto.png\', function(){setODMLayerImage(\'map_odm_orthophoto.png\')}, function(){setODMLayerImage(\'placeholder_map.png\')});\r\n\r\nODM.on(\'click\', function(e) {\r\n   checkImage(\'map_odm_orthophoto.png\', function(){setODMLayerImage(\'map_odm_orthophoto.png\')}, function(){setODMLayerImage(\'placeholder_map.png\')});\r\n\r\n});")

        file_desciptor.write("function highlightFeature(e) {\n" \
                             "	if(!inMeasureMode) {\n" \
                             "	if(mapOverlayOpacity > threshold) {\n" \
                             "		var layer = e.target;\n" \
                             "		layer.setStyle({\n" \
                             "			fillOpacity: 0.7\n" \
                             "		});\n" \
                             "	}\n" \
                             "	}\n" \
                             "}\n" \
                             "\n" \
                             "function resetHighlight(e) {\n" \
                             "	var layer = e.target;\n" \
                             "	\n" \
                             "	layer.setStyle({\n" \
                             "		fillOpacity: 0\n" \
                             "	});\n" \
                             "}\n" \
                             "\n" \
                             "var polygons;\n" \
                             "function loadPolygons() {\n" \
                             "	polygons = new Array();\n" \
                             "  var centers = new Array();\n" \
                             "	var svg = document.getElementById(\'overviewMap\').getElementsByTagName(\'polyline\');\n" \
                             "	for (var i = 0; i < svg.length; i++) {\n" \
                             "		for (var j = 0; j < svg[i][\'points\'].length; j++) {			\n" \
                             "		}\n" \
                             "		//var names really bad, myb adjust\n" \
                             "		var p1=[svg[i][\'points\'][0][\'x\']/mapSize[0],svg[i][\'points\'][0][\'y\']/mapSize[1]];\n" \
                             "		var p2=[svg[i][\'points\'][1][\'x\']/mapSize[0],svg[i][\'points\'][1][\'y\']/mapSize[1]];\n" \
                             "		var p3=[svg[i][\'points\'][2][\'x\']/mapSize[0],svg[i][\'points\'][2][\'y\']/mapSize[1]];\n" \
                             "		var p4=[svg[i][\'points\'][3][\'x\']/mapSize[0],svg[i][\'points\'][3][\'y\']/mapSize[1]];\n" \
                             "		var pL1 = [p1[1] * lat1 + ((1 - p1[1]) * lat2),p1[0] * long2 + ((1 - p1[0]) * long1)];\n" \
                             "		var pL2 = [p2[1] * lat1 + ((1 - p2[1]) * lat2),p2[0] * long2 + ((1 - p2[0]) * long1)];\n" \
                             "		var pL3 = [p3[1] * lat1 + ((1 - p3[1]) * lat2),p3[0] * long2 + ((1 - p3[0]) * long1)];\n" \
                             "		var pL4 = [p4[1] * lat1 + ((1 - p4[1]) * lat2),p4[0] * long2 + ((1 - p4[0]) * long1)];\n" \
                             "		var latlngs = [pL1,pL2,pL3,pL4];\n" \
                             "      var center = [((pL1[0] + pL3[0]) / 2.0), ((pL1[1] + pL3[1]) / 2.0)];\n" \
                             "      centers.push(center);\n" \
                             "		var polygon = L.polygon(latlngs ,{ opacity: 0, fillOpacity: 0, fillColor: '#0000FF' });\n" \
                             "		polygon.on(\'mouseover\', highlightFeature);\n" \
                             "		polygon.on(\'mouseout\', resetHighlight);\n" \
                             "		polygon.on(\'click\',	slide);\n" \
                             "           mapOverlay.addLayer(polygon);\n" \
                             "		polygons.push(polygon);\n" \
                             "	}\n" \
                             "  trajectory = L.polyline(centers);\n" \
                             "  var overlay = {\n" \
                             "  'Gpx': trajectory\n" \
                             "  };\n" \
                             "  var gpxLayer = L.control.layers(null, overlay, {\n" \
                             "  collapsed: false,\n" \
                             "  position: 'topleft'\n" \
                             "  });\n" \
                             "  gpxLayer.addTo(map);\n" \
                             "  document.getElementById(\'secondMap\').remove();\n" \
                             "}\n" \
                             "\n" \
                             "function slide(e) {\n" \
                             "	var i = polygons.indexOf(e.target);\n" \
                             "	currentSlide(i+1);\n" \
                             "}\n" \
                             "\n" \
                             "function changeAlpha(value) {\n" \
                             "    mapImage.setOpacity(value/100);\n")
        if (self.with_odm):
            file_desciptor.write("    ODM.setOpacity(value/100);\n")

        file_desciptor.write("    mapOverlayOpacity = value/100;\n" \
                             "}\n" \
                             "<!-- home button functionality -->\n" \
                             "L.Control.zoomHome = L.Control.extend({\n" \
                             "options: {\n" \
                             "position: \'topleft\',\n" \
                             "zoomHomeText: \'&#9873;\',\n" \
                             "zoomHomeTitle: \'Zoom home\'\n" \
                             "},\n" \
                             "onAdd: function (map) {\n" \
                             "var controlName = \'gin-control-zoom\',\n" \
                             "container = L.DomUtil.create(\'div\', controlName + \' leaflet-bar\'),\n" \
                             "options = this.options;\n" \
                             "//container.innerHTML\n" \
                             "this._zoomHomeButton = this._createButton(options.zoomHomeText, options.zoomHomeTitle,\n" \
                             "controlName + \'-home\', container, this._zoomHome);\n" \
                             "return container;\n" \
                             "},\n" \
                             "onRemove: function (map) {\n" \
                             "},\n" \
                             "_zoomHome: function (e) {\n" \
                             "map.flyTo(center, defaultZoom);\n" \
                             "},\n" \
                             "_createButton: function (html, title, className, container, fn) {\n" \
                             "var link = L.DomUtil.create(\'a\', className, container);\n" \
                             "link.innerHTML = html;\n" \
                             "link.href = \'#\';\n" \
                             "link.title = title;\n" \
                             "link.role = \"button\";\n" \
                             "L.DomEvent\n" \
                             ".on(link, \'click\', fn, this)\n" \
                             ".on(link, \'click\', L.DomEvent.stop)\n" \
                             ".on(link, \'click\', this._refocusOnMap, this);;\n" \
                             "return link;\n" \
                             "},\n" \
                             "});\n" \
                             "var zoomHome = new L.Control.zoomHome();\n" \
                             "zoomHome.addTo(map);\n" \
                             "<!-- home button functionality -->\n" \
                             "var layerswitcher = {\n" \
                             "RGB: mapOverlay" )

        if (self.with_odm):
            file_desciptor.write(",\nODM: odmOverlay\n")

        file_desciptor.write("};\n" \
                             "L.control.layers(layerswitcher,{}, {collapsed: false}).addTo(map);\n" \
                             "layerswitcher.RGB.addTo(map);\n" \
                             "</script>\n" \
                             "\n" \
                             "<script>\n" \
                             "function changeAlpha2(value) {\n" \
                             "	var map = document.getElementById(\"overviewMap\");\n" \
                             "	map.setAttribute(\"opacity\", value/100);\n" \
                             "}\n" \
                             "</script>")


    def write_summary(self, file_desciptor):
        file_desciptor.write("<h1 style=\"text-align: center;margin-top:2%; color: white; font-size: 500%\">Flight Report</h1>\n"\
        "<h2 style=\"text-align: center;margin-top:5%; color: white; font-size: 300%\">Flight Information</h2>\n"\
        "<table class=\"tg\">\n"\
        "   <tr>\n"\
        "      <td class=\"tg-031e\">Date</td>\n"\
        "      <td class=\"tg-031e\">"+'.'.join(str(self.date).split(" ")[0].split(":")[::-1])+"</td>\n"\
        "   </tr>\n"\
        "   <tr>\n"\
        "      <td class=\"tg-031e\">Time</td>\n"\
        "      <td class=\"tg-031e\">"+str(self.date).split(" ")[-1]+"</td>\n"\
        "   </tr>\n"\
        "   <tr>\n"\
        "      <td class=\"tg-031e\">Location</td>\n"\
        "      <td class=\"tg-031e\">"+str(self.location)+"</td>\n"\
        "   </tr>\n"\
        "   <tr>\n"\
        "      <td class=\"tg-031e\">Area Coverd</td>\n"\
        "      <td class=\"tg-031e\">"+str(self.area_k)+str(" km")+"<sup>2</sup></td>\n"\
        "   </tr>\n"\
        "   <tr>\n"\
        "      <td class=\"tg-031e\">Flight Time</td>\n"\
        "      <td class=\"tg-031e\">"+str(self.flight_time_str)+"</td>\n"\
        "   </tr>\n"\
        "   <tr>\n"\
        "      <td class=\"tg-031e\">Processing Time</td>\n"\
        "      <td class=\"tg-031e\">"+str(self.processing_time).split(":")[0]+" h : " +str(self.processing_time).split(":")[1]+" m : "+str(self.processing_time).split(":")[2][0:2]+" s</td>\n"\
        "   </tr>\n"\
        "   <tr>\n"\
        "      <td class=\"tg-031e\">Images</td>\n"\
        "      <td class=\"tg-031e\">"+str(len(self.map_elements))+"</td>\n"\
        "   </tr>\n"\
        "   <tr>\n"\
        "      <td class=\"tg-031e\">Image Resolution</td>\n"\
        "      <td class=\"tg-031e\">"+str(self.x_res)+" &#10799; "+str(self.y_res)+" px</td>\n"\
        "   </tr>\n"\
        "   <tr>\n"\
        "      <td class=\"tg-031e\">Avg. Flight Height</td>\n"\
        "      <td class=\"tg-031e\">"+str(int(float(self.avg_altitude)))+" m</td>\n"\
        "   </tr>\n"\
        "</table>\n"\
        "\n"\
        "<h2 style=\"text-align: center;margin-top:5%; color: white; font-size: 300%\">Camera Specification</h2>\n"\
        "<table class=\"tg\">\n"\
        "   <tr>\n"\
        "      <td class=\"tg-031e\">Camera Model</td>\n"\
        "      <td class=\"tg-031e\">"+str(self.camera_model)+"</td>\n"\
        "   </tr>\n"\
        "   <tr>\n"\
        "      <td class=\"tg-031e\">Focal Length</td>\n"\
        "      <td class=\"tg-031e\">"+str(self.camera_focal_length)+" mm</td>\n"\
        "   </tr>\n"\
        "   <tr>\n"\
        "      <td class=\"tg-031e\">Horizontal FOV</td>\n"\
        "      <td class=\"tg-031e\">"+str(self.camera_fov)+" &deg;</td>\n"\
        "   </tr>\n"\
        "   <tr>\n"\
        "      <td class=\"tg-031e\">Vertical FOV</td>\n"\
        "      <td class=\"tg-031e\">"+str(round(self.camera_vertical_fov, 1))+" &deg;</td>\n"\
        "   </tr>\n"\
        "   <tr>\n"\
        "      <td class=\"tg-031e\">Sensor Size</td>\n"\
        "      <td class=\"tg-031e\">"+str(round(self.sensor_width, 2))+" &#10799; "+str(round(self.sensor_height, 2))+" mm</td>\n"\
        "   </tr>\n"\
        "</table>\n"\
        "\n"\
        "<h2 style=\"text-align: center;margin-top:5%; color: white; font-size: 300%\">Weather</h2>\n"\
        "<table class=\"tg\">\n"\
        "   <tr>\n"\
        "      <td class=\"tg-031e\">Temperature</td>\n"\
        "      <td class=\"tg-031e\">"+str(self.temperature)+" &deg;C</td>\n"\
        "   </tr>\n"\
        "   <tr>\n"\
        "      <td class=\"tg-031e\">Humidity</td>\n"\
        "      <td class=\"tg-031e\">"+str(self.humidity)+" %</td>\n"\
        "   </tr>\n"\
        "   <tr>\n"\
        "      <td class=\"tg-031e\">Air Pressure</td>\n"\
        "      <td class=\"tg-031e\">"+str(self.altimeter)+" mb</td>\n"\
        "   </tr>\n"\
        "   <tr>\n"\
        "      <td class=\"tg-031e\">Wind Speed</td>\n"\
        "      <td class=\"tg-031e\">"+str(self.wind_speed)+str(" m/s")+" &#8776; "+str(round(self.wind_speed*3.6, 1))+" km/h </td>\n"\
        "   </tr>\n"\
        "   <tr>\n"\
        "      <td class=\"tg-031e\">Wind Direction</td>\n"\
        "      <td class=\"tg-031e\">"+str(self.wind_dir_degrees)+"&deg; &nbsp; <div style=\"transform: rotate("+str(int(self.wind_dir_degrees)+45)+"deg);display: inline-block;font-size: 40px;\">  &#9099;</div></td>\n"\
        "   </tr>\n"\
        "   <tr>\n"\
        "      <td class=\"tg-031e\">Visibility</td>\n"\
        "      <td class=\"tg-031e\">"+str(self.visibility)+" km</td>\n"\
        "   </tr>\n"\
        "</table>\n"\
        "<h2 style=\"text-align: center;margin-top:5%; color: white; font-size: 300%;padding-bottom:30px;\">Profiles</h2>\n"\
        "<img class=\"tg\" src=\"speed_elevation_profile.png\" style=\"display: block;\">\n")


    def extract_coordinates(self):
        for map_element in self.map_elements:

            image = map_element.get_image().get_matrix()
            rect = map_element.get_rotated_rectangle()
            coordinates = rect.get_contour().exterior.coords[:]
                
            tmp_coordinates = list()
            for coordinate in coordinates:
                x, y = coordinate
                tmp_coordinates.append(int(x))
                tmp_coordinates.append(int(self.map_height - y))

            str_coordinates = ','.join(str(e) for e in tmp_coordinates)
            self.new_coordinates.append(str_coordinates)
