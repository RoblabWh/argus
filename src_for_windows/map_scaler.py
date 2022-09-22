#!/usr/bin/env python3
__author__      = "Artur Leinweber"
__copyright__ = "Copyright 2020"
__credits__ = ["None"]
__license__ = "GPL"
__version__ = "1.0.1"
__maintainer__ = "Artur Leinweber"
__email__ = "arturleinweber@live.de"
__status__ = "Production"

import numpy as np
import math
import webbrowser

from map_element import MapElement
from rectangle import RotatedRect
from gps import GPS

import matplotlib.pyplot as plt
import numpy as np
from descartes import PolygonPatch

class MapScaler:

    def __init__(self, images, map_width_px, map_height_px):
        self.map_elements = list()
        self.images = images
        
        self.scaled_points = list()
        self.scale_px_per_m = 0
        self.scale_px_per_m_image = 0
        
        self.distances_m = list()
        self.distances_px = list()
        

        self.map_width = map_width_px
        self.map_height = map_height_px
        self.map_offset = 0

        self.length_w_in_m, self.length_h_in_m = MapScaler.calc_length_via_fov(images)

        #print("length_w_in_m:", self.length_w_in_m)
        #print("length_h_in_m:", self.length_h_in_m)

        #print(images[0].get_width()/self.length_w_in_m[0])
        #print(images[0].get_height()/self.length_h_in_m[0])
        #exit()
        #print("\n")

        self.calc_scale_px_per_m(*(self.get_min_and_max_scales()))
        self.create_map_elements()
        #self.plot_trajectory()
        #exit()        

    def plot_polygons(self):
        self.plot_polygons()

    def calib(self):
        gps0 = self.images[0].get_exif_header().get_gps()
        gps1 = self.images[1].get_exif_header().get_gps()
        lat0, lon0, alt0 = (gps0.get_latitude(), gps0.get_longitude(), gps0.get_altitude())
        lat1, lon1, alt1 = (gps1.get_latitude(), gps1.get_longitude(), gps1.get_altitude())         
        x0, y0 = gps0.get_cartesian()
        #print(lat0)
        #print(lon0)
        gps_lat = GPS(lat0 + (lat0-lat1), lon0, alt0)
        gps_lon = GPS(lat0, lon0 + (lon0-lon1), alt0)
        gps_lat_lon = GPS(lat0 + (lat0-lat1), lon0 + (lon0-lon1), alt0)
        x_lat, y_lat = gps_lat.get_cartesian()
        x_lon, y_lon = gps_lon.get_cartesian()
        x_lat_lon, y_lat_lon = gps_lat_lon.get_cartesian() 

        min_x = min(x0, x_lat, x_lon, x_lat_lon)
        max_x = max(x0, x_lat, x_lon, x_lat_lon)
        min_y = min(y0, y_lat, y_lon, y_lat_lon)
        max_y = max(y0, y_lat, y_lon, y_lat_lon)

        x0 = ((x0 - min_x) / (max(max_x-min_x, max_y-min_y))) * self.map_width
        y0 = ((y0 - min_y) / (max(max_x-min_x, max_y-min_y))) * self.map_width
        x_lat = ((x_lat - min_x) / (max(max_x-min_x, max_y-min_y))) * self.map_width
        y_lat = ((y_lat - min_y) / (max(max_x-min_x, max_y-min_y))) * self.map_width
        x_lon = ((x_lon - min_x) / (max(max_x-min_x, max_y-min_y))) * self.map_width
        y_lon = ((y_lon - min_y) / (max(max_x-min_x, max_y-min_y))) * self.map_width
        x_lat_lon = ((x_lat_lon - min_x) / (max(max_x-min_x, max_y-min_y))) * self.map_width
        y_lat_lon = ((y_lat_lon - min_y) / (max(max_x-min_x, max_y-min_y))) * self.map_width

        #horizontal - x
        d_m_x = GPS.calc_distance_between(gps0, gps_lat)

        #vertical- y
        d_m_y = GPS.calc_distance_between(gps0, gps_lon)

        #diagonal - x - y
        d_m_x_y = GPS.calc_distance_between(gps0, gps_lat_lon)

        #horizontal - x
        d_px_x = math.sqrt(((x0-x_lat)*(x0-x_lat))+((y0-y_lat)*(y0-y_lat)))

        #vertical - y
        d_px_y = math.sqrt(((x0-x_lon)*(x0-x_lon))+((y0-y_lon)*(y0-y_lon)))

        #diagonal - x - y 
        d_px_x_y = math.sqrt(((x0-x_lat_lon)*(x0-x_lat_lon))+((y0-y_lat_lon)*(y0-y_lat_lon)))

        #print("d_px_x, d_px_y",d_px_x, d_px_y)
        #print(d_px_x/ d_px_y)

        #d_px_x_y = math.sqrt(((x_lon-x_lat)*(x_lon-x_lat))+((y_lon-y_lat)*(y_lon-y_lat)))
        #print("d_px_x, d_px_y, d_px_x_y",d_px_x, d_px_y, d_px_x_y)
        px_per_m_in_x = d_px_x / d_m_x
        px_per_m_in_y = d_px_y / d_m_y
        px_per_m_in_x_y = d_px_x_y / d_m_x_y
        #print("px_per_m_in_x:", px_per_m_in_x)
        #print("px_per_m_in_y:", px_per_m_in_y)
        #print("px_per_m_in_x_y:", px_per_m_in_x_y)

        #y_scale = px_per_m_in_x / px_per_m_in_y
        #x_scale = px_per_m_in_y / px_per_m_in_x
        
        #print("y_scale: ", y_scale)
        #print("x_scale: ",x_scale)
        #return x_scale, y_scale

    def get_min_and_max_scales(self):
        #Searching for Min and Max of X and Y for creating our Map
        min_x = float("inf")
        min_y = float("inf")
        max_x = float("-inf")
        max_y = float("-inf")

        for image in self.images:
            x, y = image.get_exif_header().get_gps().get_cartesian()
            if (min_x > x):
                min_x = x

            if (min_y > y):
                min_y = y

            if (max_x < x):
                max_x = x

            if (max_y < y):
                max_y = y
        #print(min_x, max_x, min_y, max_y)
        return min_x, max_x, min_y, max_y

    def calc_scale_px_per_m(self, min_x, max_x, min_y, max_y):
        distances_m = list()
        distances_px = list()

        #self.calib()
        x_coord = list()
        y_coord = list()

        for image in self.images:
            x, y = image.get_exif_header().get_gps().get_cartesian()
            #x = int(((float(x-min_x) / float(max_x - min_x)) * self.map_width))
            #y = int(((float(y-min_y) / float(max_y - min_y)) * self.map_height))
            x = (float(x - min_x)  / float(max(max_x-min_x, max_y-min_y))) * self.map_width
            y = (float(y - min_y)  / float(max(max_x-min_x, max_y-min_y))) * (self.map_width)
            
            #print("(x,y): ",x,",",y)
            x_coord.append(x)
            y_coord.append(y)
            self.scaled_points.append((x, y))
        
        #fig = plt.figure("Projection", figsize=(10, 10))
        #ax = fig.add_subplot(121)
        #ax = plt.gca()
        #ax.axis('equal')
        #ax.set_xlim(min(x_coord)-100, max(x_coord)+100)
        #ax.set_ylim(min(y_coord)-100, max(y_coord)+100)
        #print("scaled_points:", self.scaled_points)
        #plt.plot(x_coord, y_coord)
        #plt.plot(x_coord, y_coord,'o')  
        #plt.show()

        for i in range(len(self.scaled_points)-1):
            x1,y1 = self.scaled_points[i]
            x2,y2 = self.scaled_points[i+1]
            distances_px.append(math.sqrt(((x1-x2)*(x1-x2))+((y1-y2)*(y1-y2))))        

        for i in range(len(self.images)-1):
            gps1 = self.images[i].get_exif_header().get_gps()
            gps2 = self.images[i+1].get_exif_header().get_gps()
            distances_m.append(GPS.calc_distance_between(gps1, gps2))
 
        #print("distances_px:", distances_px)
        #print("\n")
        #print("distances_m:", distances_m)
        
        scale_px_per_m_lst = list()
        for i in range(len(self.images)-1):
            #self.scale_px_per_m_lst[i] = (distances_px[i] / distances_m[i])
            #self.scale_px_per_m = self.scale_px_per_m + (distances_m[i] / distances_px[i])
            #print(i+1,":",distances_px[i] / distances_m[i])
            if distances_m[i] > 0:
                scale_px_per_m_lst.append(distances_px[i] / distances_m[i])
            
        self.scale_px_per_m = np.mean(np.asarray(scale_px_per_m_lst))
        #min(scale_px_per_m_lst) / max(scale_px_per_m_lst)
        #print ("self.scale_px_per_m:", self.scale_px_per_m)


        #self.scale_x = minimum/maximum
        #print(self.scale_x, self.scale_y)
        #print("\n")

    def create_map_elements(self):
        #new
        #for i in range(len(self.images)):
        #    self.scale_px_per_m_image = self.scale_px_per_m_image + (self.images[i].get_width() / self.length_w_in_m[i])
        #    self.scale_px_per_m_image = self.scale_px_per_m_image + (self.images[i].get_height() / self.length_h_in_m[i])
        #
        #self.scale_px_per_m_image = self.scale_px_per_m_image/(len(self.images) * 2)
        #----     


        image_width_px = list()
        image_height_px = list()
        for i in range(len(self.images)):
            image_width_px.append(int(self.length_w_in_m[i] * self.scale_px_per_m))
            image_height_px.append(int(self.length_h_in_m[i] * self.scale_px_per_m))
            #image_width_px.append(int(self.images[i].get_width() / self.scale_px_per_m_image * self.scale_px_per_m))
            #image_height_px.append(int(self.images[i].get_height() / self.scale_px_per_m_image * self.scale_px_per_m))
   
        #print("image_width_px:", image_width_px, "\n")
        #print("image_height_px:", image_height_px, "\n")
        self.map_offset = int(math.sqrt(((max(image_width_px))*(max(image_width_px)))+((max(image_height_px))*(max(image_height_px)))) * 2)
        
        #print("self.map_offset:", self.map_offset)
        #print("\n")
        #yaw = 0
        #for i in range(len(self.images)):
        #    dif = abs(self.images[i].get_exif_header().get_xmp().get_flight_yaw_degree() - self.images[i].get_exif_header().get_xmp().get_gimbal_yaw_degree())
        #    yaw = yaw + dif
        #ref = yaw/len(self.images)
        ref = self.images[1].get_exif_header().get_xmp().get_flight_yaw_degree() - self.images[1].get_exif_header().get_xmp().get_gimbal_yaw_degree()
        #print(ref) 
        for i in range(len(self.images)):
            image = self.images[i]
            cx, cy = self.scaled_points[i]
            gimbal_yaw_degree = -(image.get_exif_header().get_xmp().get_gimbal_yaw_degree() + ref)
            self.map_elements.append(MapElement(image, RotatedRect(int(self.map_offset/2) + cx, int(self.map_offset/2) + cy , image_width_px[i], image_height_px[i], gimbal_yaw_degree)))
    
    def plot_polygons(self):
        fig = plt.figure("Projection", figsize=(10, 10))
        #ax = fig.add_subplot(121)
        ax = plt.gca()
        ax.axis('equal')
        ax.set_xlim(0, self.map_offset + self.map_width)
        ax.set_ylim(0, self.map_height + self.map_offset)
        
        for i in range(len(self.map_elements)-1):
            r1 = self.map_elements[i].get_rotated_rectangle()
            r2 = self.map_elements[i + 1].get_rotated_rectangle()
            x1, y1 = r1.get_center()
            x2, y2 = r2.get_center()
            ax.add_patch(PolygonPatch(r1.get_contour(), fc='#'+ str(100000+i), alpha=0.7))
            ax.add_patch(PolygonPatch(r2.get_contour(), fc='#'+ str(100000+i+1), alpha=0.7))
            #plt.plot(x1, y1)
            #plt.plot(x2, y2)
            #plt.plot(x1, y1,'o')
            #plt.plot(x2, y2,'o')
            #intersection_polygon = r2.intersection(r1)
            #ax.add_patch(PolygonPatch(intersection_polygon, fc='#'+str(100000 + (2 * i + 1)), alpha=1))

        
        x_coord = [((x_tuple.get_rotated_rectangle().get_center())[0]) for x_tuple in self.map_elements]
        y_coord = [((y_tuple.get_rotated_rectangle().get_center())[1]) for y_tuple in self.map_elements]

        #x_coord = [(x_tuple[0]+self.map_offset/2) for x_tuple in self.scaled_points]
        #y_coord = [(y_tuple[1]+self.map_offset/2) for y_tuple in self.scaled_points]
        #print(x_coord)
        #print(y_coord)
        plt.plot(x_coord, y_coord)
        plt.plot(x_coord, y_coord,'o')  
        plt.show()

    def plot_trajectory(self):
        ax = plt.gca()
        ax.axis('equal')
        x_coord = [x_tuple[0] for x_tuple in self.scaled_points]
        y_coord = [y_tuple[1] for y_tuple in self.scaled_points]
        #print(x_coord)
        #print(y_coord)
        plt.plot(x_coord, y_coord)
        plt.show()

    def get_map_offset(self):
        return self.map_offset

    def get_map_elements(self):
        return self.map_elements

    def get_area_in_m(self):
        max_x = float("-inf")
        max_y = float("-inf")
        for point in self.scaled_points:
            x, y = point
            if (max_x < x):
                max_x = x

            if (max_y < y):
                max_y = y
        return max_x/self.scale_px_per_m * max_y/self.scale_px_per_m 

    def get_avg_altitude(self):
        avg_altitude = 0
        for map_element in self.map_elements:
            avg_altitude = avg_altitude + map_element.get_image().get_exif_header().get_gps().get_altitude()
        avg_altitude = str(avg_altitude/len(self.map_elements))
        return avg_altitude

    @staticmethod
    def calc_length_via_fov(images):
        length_w_in_m = list()
        length_h_in_m = list()
        vertical_fov = 0
        horizontal_fov = 0
        sensor_width_mm = 0
        sensor_height_mm = 0

        for image in images:
            image_header = image.get_exif_header()
            relative_altitude = image_header.get_gps().get_altitude()
            camera_properties = image_header.get_camera_properties()
            focal_length = camera_properties.get_focal_length()
            horizontal_fov = camera_properties.get_fov()
            image_width = image.get_width()
            image_height = image.get_height()

            sensor_width_mm = math.tan(math.radians(horizontal_fov)/2) * (2*focal_length)
            #print(sensor_width_mm) 
            sensor_height_mm = sensor_width_mm/(image_width/image_height)
            #print(sensor_height_mm)
            vertical_fov = math.degrees(2*math.atan2(sensor_height_mm/2,focal_length))            
            
            camera_properties.set_sensor_size(sensor_width_mm, sensor_height_mm)
            camera_properties.set_vertical_fov(vertical_fov)
            #print("relative_altitude:", relative_altitude)
            roh_horizontal = 180.0 - 90.0 - (horizontal_fov / 2.0)
            roh_vertical = 180.0 - 90.0 - (vertical_fov / 2.0)
            horizontal_length_m = (relative_altitude * 2.0) / (np.tan(np.deg2rad(roh_horizontal)))
            vertical_length_m = (relative_altitude * 2.0) / (np.tan(np.deg2rad(roh_vertical)))
            length_w_in_m.append(horizontal_length_m)
            length_h_in_m.append(vertical_length_m)
        return (length_w_in_m, length_h_in_m)

    def get_middle_gps(self):
        return (self.map_elements[int(len(self.map_elements)/2)].get_image().get_exif_header().get_gps())

    def get_scale_px_per_m(self):
        return self.scale_px_per_m

    def get_scale_m_per_px(self):
        return 1.0/self.scale_px_per_m

    def calculate_distance_between_corner_and_origin_in_px(self, corner_location, origin_location):
        x_corner, y_corner = corner_location
        x_origin, y_origin = origin_location

        distance = math.sqrt(math.pow(x_corner - x_origin, 2) + math.pow(y_corner - y_origin, 2))
        #print("Distance to Corner:" + str(distance) + "[px]")
        return distance

    def calculate_distance_between_object_and_uav_in_m(self, corner_location, origin_location):
        x_origin, y_origin = origin_location
        x_corner, y_corner = corner_location

        x_corner = x_corner * self.get_scale_m_per_px()
        y_corner = y_corner * self.get_scale_m_per_px()

        x_origin = x_origin * self.get_scale_m_per_px()
        y_origin = y_origin * self.get_scale_m_per_px()

        distance_m = math.sqrt(math.pow(x_corner-x_origin, 2) + math.pow(y_corner-y_origin, 2))
        #print("Distance to Corner:" + str(distance_m) + "[m]")
        return distance_m

    def calculate_angle_distance_between_corner_and_origin(self, distance, corner_location, origin_location):

        x_origin, y_origin = origin_location
        x_corner, y_corner = corner_location
        #print("x_origin, y_origin: ", x_origin, y_origin)
        #calculate_angle_distance_between_object_and_uav
        if((y_origin - y_corner) >= 0):
            if (x_corner - x_origin == 0):
                return 0
                             
            rad = (math.acos((x_corner - x_origin) / distance))
        else:
            rad = 2 * math.pi - (math.acos((x_corner - x_origin) / distance))

        grad = math.degrees(rad)
        #print "Grad: " + str(grad)
        if ((grad - 90) < 0 ):
            grad = 360 - (90 - grad)

        else:
            grad = grad - 90
        
        return grad



    def calculate_corner_gps_coordinates(self, origin_gps, origin_location, corner_location):
        CONST_RADIUS_EARTH_METER = 6378137.000
        distance_px = self.calculate_distance_between_corner_and_origin_in_px(corner_location, origin_location)
        distance = self.calculate_distance_between_object_and_uav_in_m(corner_location, origin_location)
        angle = self.calculate_angle_distance_between_corner_and_origin(distance_px, corner_location, origin_location)
        # Vielleicht muss eine Fallunterscheidung hin wegen -180 und +180
        #new_angle = (self.uav_flight_yaw_degree + 540) % 360 - angle
        #new_angle = (-angle + 540) % 360 - 180
        new_angle = angle + 180
     
        #print(new_angle)

        origin_gps_latitude = origin_gps.get_latitude()# - 0.00005
        origin_gps_longitude = origin_gps.get_longitude()# - 0.0001

        new_latitude = math.asin(math.sin(math.radians(origin_gps_latitude)) *
                                 math.cos(distance / CONST_RADIUS_EARTH_METER) +
                                 math.cos(math.radians(origin_gps_latitude)) *
                                 math.sin(distance / CONST_RADIUS_EARTH_METER) *
                                 math.cos(math.radians(new_angle)))

        new_longitude = math.radians(origin_gps_longitude) + \
                        math.atan2(math.sin(math.radians(new_angle)) *
                                   math.sin(distance / CONST_RADIUS_EARTH_METER) *
                                   math.cos(math.radians(origin_gps_latitude)),
                                   math.cos(distance / CONST_RADIUS_EARTH_METER) -
                                   math.sin(math.radians(origin_gps_latitude))*math.sin(new_latitude))
        lat = math.degrees(new_latitude)
        lng = math.degrees(new_longitude)
        #webbrowser.open("https://www.google.com/maps/search/?api=1&query="+str(lat)+","+str(lng)) 
        return GPS(self.get_avg_altitude(),lat,lng)



