#!/usr/bin/env python3
__author__      = "Artur Leinweber"
__copyright__ = "Copyright 2020"
__credits__ = ["None"]
__license__ = "GPL"
__version__ = "1.0.1"
__maintainer__ = "Artur Leinweber"
__email__ = "arturleinweber@live.de"
__status__ = "Production"

import math
import numpy as np
from vincenty import vincenty
from geopy.geocoders import Nominatim
#from pyproj import Transformer
import utm

class GPS:
    def __init__(self, altitude, latitude, longitude):
        """
        Constructor
        :param altitude: altitude
        :param latitude: latitude
        :param longitude: longitude
        """
        self.altitude = altitude
        self.latitude = latitude
        self.longitude = longitude

    def __str__(self):
        """
        Represent the string interpretation of an gps coordinate.
        :return: string representation
        """
        return "altitude: " + str(self.altitude) + "\n" \
               + "latitude: " + str(self.latitude) + "\n" \
               + "longitude: " + str(self.longitude) + "\n"

    def get_latitude(self):
        """
        Returning latitude.
        :return: latitude
        """
        return self.latitude

    def get_longitude(self):
        """
        Returning longitude.
        :return: longitude
        """
        return self.longitude

    def get_altitude(self):
        """
        Returning altitude.
        :return: altitude
        """
        return self.altitude

    def get_address(self):
        geolocator = Nominatim(user_agent="12879379127889378123")
        location = geolocator.reverse(str(self.latitude) + " " + str(self.longitude))
        return str(location.address)

#    def get_cartesian_works(self):
#        lat = self.latitude
#        lon = self.longitude
#        lat, lon = np.deg2rad(lat), np.deg2rad(lon)
#        R = 6373000 # radius of the earth
#        x = R * np.cos(lat) * np.cos(lon)
#        y = R * np.cos(lat) * np.sin(lon)
#        z = R *np.sin(lat)
#        #return np.cos(np.deg2rad(45)) * x , np.sin(np.deg2rad(45)) * y
#        return y , -x
    
#    def get_cartesian(self):
#        x, y, zone_number, zone_letter = utm.from_latlon(self.latitude, self.longitude)
#        return x, y

#    def get_cartesian(self):
#        WGS84_a = 6378137.0
#        WGS84_b = 6356752.314245
#        a2 = WGS84_a ** 2
#        b2 = WGS84_b ** 2
#        lat = np.radians(self.latitude)
#        lon = np.radians(self.longitude)
#        alt = self.altitude
#        L = 1.0 / np.sqrt(a2 * np.cos(lat) ** 2 + b2 * np.sin(lat) ** 2)
#        x = (a2 * L + alt) * np.cos(lat) * np.cos(lon)
#        y = (a2 * L + alt) * np.cos(lat) * np.sin(lon)
#        z = (b2 * L + alt) * np.sin(lat)
#        return y, -x#, z

    def get_cartesian(self):
        lats, lons = self.latitude, self.longitude
        r_major = 6378137.000
        x = r_major * np.radians(lons)
        scale = x/lons
        y = 180.0/np.pi * np.log(np.tan(np.pi/4.0 + lats * (np.pi/180.0)/2.0)) * scale
        return (x, y)

#    def get_cartesian(self):
#        TRAN_4326_TO_3857 = Transformer.from_crs("EPSG:4326", "EPSG:3857")
#        return TRAN_4326_TO_3857.transform(self.longitude, self.latitude)

#    def get_cartesian(self):
#        latitude, longitude = self.latitude, self.longitude
#        mWorldWidth = 6371.0
#        x = longitude / 360 + 0.5
#        siny = np.sin(np.deg2rad(latitude))
#        y = 0.5 * np.log((1 + siny) / (1 - siny)) / -(2 * math.pi) + 0.5
#        print(x * mWorldWidth, y * mWorldWidth)
#        return x * mWorldWidth, -y * mWorldWidth 

    #https://en.wikipedia.org/wiki/Equal_Earth_projection
    #def get_cartesian(self):
    #    lat = self.latitude
    #    lon = self.longitude
    #    lat, lon = np.deg2rad(lat), np.deg2rad(lon)
    #    #R = 6373000 # radius of the earth
    #    A1 = 1.340264
    #    A2 = -0.081106
    #    A3 = 0.000893
    #    A4 = 0.003796
    #    ROH = math.asin((math.sqrt(3)/2) * math.sin(lat))
    #    x = (2 * math.sqrt(3) * lon * math.cos(ROH)) / (3 * (9 * A4 * ROH**8 + 7 * A3 * ROH**6 + 3 * A2 * ROH**2 + A1))
    #    y = A4 * ROH**9 + A3 * ROH**7 + A2 * ROH**3 + A1*ROH
        
        #return np.cos(np.deg2rad(45)) * x , np.sin(np.deg2rad(45)) * y
   #     return x , y
    # Mercator
#    def get_cartesian(self):
#        latitude = self.latitude
#        longitude = self.longitude
#        mWorldWidth = 6371.0
#        x = longitude / 360 + 0.5
#        siny = np.sin(np.deg2rad(latitude))
#        y = 0.5 * np.log((1 + siny) / (1 - siny)) / -(2 * math.pi) + 0.5
#        #print(x * mWorldWidth, y * mWorldWidth)
#        return (x * mWorldWidth, y * mWorldWidth)   


    #GPSUtils
    @staticmethod
    def gms_to_dg(coordinate):
        """
        Converting GMS to DG.
        :param coordinate: gps coordinate
        :return: gps coordinate in DG
        """
        grad = float(coordinate[0])
        minutes = float(coordinate[1])
        seconds = float(coordinate[2])

        return (((seconds / 60) + minutes) / 60) + grad
    
    #https://en.wikipedia.org/wiki/Equirectangular_projection
    @staticmethod
    def get_equirectangular(lat=None,lon=None):
        lat, lon = np.deg2rad(lat), np.deg2rad(lon)
        RADIUS = 6371000 # radius of the earth in meters
        x = RADIUS * lon * np.cos(lat)
        y = RADIUS * lat
        return x,y

    @staticmethod
    def convertGpsToECEF(lat, longi, alt):
        a=6378.1;
        b=6356.8;
        e= 1-((b*b)/(a*a));
        N= a/(math.sqrt(1.0-(e*math.pow(np.sin(np.deg2rad(lat)), 2))));
        cosLatRad=np.cos(np.deg2rad(lat));
        cosLongiRad=np.cos(np.deg2rad(longi));
        sinLatRad=np.sin(np.deg2rad(lat));
        sinLongiRad=np.sin(np.deg2rad(longi));
        x =(N+0.001*alt)*cosLatRad*cosLongiRad;
        y =(N+0.001*alt)*cosLatRad*sinLongiRad;
        z =(((b*b)/(a*a))*N+0.001*alt)*sinLatRad;
        return x,y

    #The best i could find!
    #https://github.com/googlemaps/android-maps-utils/blob/master/library/src/com
    #// /google/maps/android/projection/SphericalMercatorProjection.java
    @staticmethod
    def mercator_projection(latitude, longitude):
        mWorldWidth = 6371.0
        x = longitude / 360 + 0.5
        siny = np.sin(np.deg2rad(latitude))
        y = 0.5 * np.log((1 + siny) / (1 - siny)) / -(2 * math.pi) + 0.5
        #print(x * mWorldWidth, y * mWorldWidth)
        return (x * mWorldWidth, y * mWorldWidth)   

    #https://www.movable-type.co.uk/scripts/latlong.html
    @staticmethod
    def calc_distance_between_epic_fail(gps1, gps2):
        lat1 = gps1.get_latitude()
        lat2 = gps2.get_latitude()
        lon1 = gps1.get_longitude()
        lon2 = gps2.get_longitude()

        R = 6371.0 * 1000.0 
        lat1 = lat1 * math.pi/180.0
        lat2 = lat2 * math.pi/180.0
        dif_lat = (lat2-lat1) * math.pi/180.0
        dif_lon = (lon2-lon1) * math.pi/180.0

        a = np.sin(dif_lat/2.0) * np.sin(dif_lat/2.0) + np.cos(lat1) * np.cos(lat2) * np.sin(dif_lon/2.0) * np.sin(dif_lon/2.0)
        c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        d = R * c
        return d

    #https://www.kite.com/python/answers/how-to-find-the-distance-between-two-lat-long-coordinates-in-python
    @staticmethod
    def calc_distance_between_works(gps1, gps2):
        R = 6371000.8
        lat1 = math.radians(gps1.get_latitude())
        lat2 = math.radians(gps2.get_latitude())
        lon1 = math.radians(gps1.get_longitude())
        lon2 = math.radians(gps2.get_longitude())
  
        dlon = lon2 - lon1
        dlat = lat2 - lat1
        a = math.sin(dlat / 2.0)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2.0)**2
        c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
        distance = R * c
        return distance

    @staticmethod
    def calc_distance_between(gps1, gps2):
        #lat1 = math.radians(gps1.get_latitude())
        #lat2 = math.radians(gps2.get_latitude())
        #lon1 = math.radians(gps1.get_longitude())
        #lon2 = math.radians(gps2.get_longitude())
        
        return vincenty((gps1.get_latitude(), gps1.get_longitude()),(gps2.get_latitude(),gps2.get_longitude())) * 1000.0

