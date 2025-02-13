import math
import numpy as np
from vincenty import vincenty
from geopy.geocoders import Nominatim
import requests
#from pyproj import Transformer
import utm

# open-meteo api for elevation data (to estimate missing relative altitude) uses the elevation data from Copernicus DEM
# see https://doi.org/10.5270/ESA-c5d3d65 for more information

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
        self.manual_altitude = False

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

    def estimate_relative_altitude(self, gps_altitude):
        # API link looks like https://api.open-meteo.com/v1/elevation?latitude={}&longitude={}
        if gps_altitude is None:
            return False

        try:
            #api works, but returns seem to be wrong
            #url = f"https://api.open-meteo.com/v1/elevation?latitude={self.latitude}&longitude={self.longitude}"
            #response = requests.get(url)
            #print("Response from open-meteo API: ", response.json(), flush=True)
            #ground_level = response.json()['elevation'][0]

            #Free API not applicable for this purpose, due to to high number of requests per second
            #url = f"https://api.opentopodata.org/v1/test-dataset?locations={self.latitude},{self.longitude}"
            #response = requests.get(url)
            #print("Response from open-meteo API: ", response.json(), flush=True)
            #ground_level = response.json()['results']['elevation']

            #google maps api
            yek = "AIzaSyBOMc1dHgyUHXj1ZrkazxgGh03h_NjjkRs"
            url = f"https://maps.googleapis.com/maps/api/elevation/json?locations={self.latitude},{self.longitude}&key={yek}"
            response = requests.get(url)
            print("Response from google maps API: ", response.json(), flush=True)
            ground_level = response.json()['results'][0]['elevation']

            relative_altitude = abs(gps_altitude - ground_level)
            print("relative altitude: ", relative_altitude, "altitude b4:", self.altitude, "gps altitude", gps_altitude, flush=True)
        except:
            return False

        if ground_level is None:
            return False

        self.altitude = relative_altitude
        return True

    def get_cartesian(self):
        lats, lons = self.latitude, self.longitude
        r_major = 6378137.000
        x = r_major * np.radians(lons)
        scale = x/lons
        y = 180.0/np.pi * np.log(np.tan(np.pi/4.0 + lats * (np.pi/180.0)/2.0)) * scale
        return (x, y)

    #GPSUtils
    @staticmethod
    def gms_to_dg(coordinate, southOrWest=False):
        """
        Converting GMS to DG.
        :param coordinate: gps coordinate
        :return: gps coordinate in DG
        """

        if southOrWest:
            return -1 * GPS.gms_to_dg(coordinate)

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
        return vincenty((gps1.get_latitude(), gps1.get_longitude()),(gps2.get_latitude(),gps2.get_longitude())) * 1000.0

