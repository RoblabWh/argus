#!/usr/bin/env python3
__author__      = "Artur Leinweber"
__copyright__ = "Copyright 2020"
__credits__ = ["None"]
__license__ = "GPL"
__version__ = "1.0.1"
__maintainer__ = "Artur Leinweber"
__email__ = "arturleinweber@live.de"
__status__ = "Production"


import json
import math
import requests
import numpy as np


class Weather:
    def __init__(self, lat, lon, api_key):
        """
        Constructor
        """
        self.api_key = api_key
        url = "https://api.openweathermap.org/data/2.5/onecall?lat=%s&lon=%s&appid=%s&units=metric" % (lat, lon, api_key)
        response = requests.get(url)
        self.data = json.loads(response.text)
        # print("Weather data for request")
        # print(url)
        # print(":")
        # print(self.data)
        # print("weather data loaded")

    def get_temperature(self):
        return self.data["current"]["temp"]
    
    def get_humidity(self):
        return str(self.data["current"]["humidity"])
    
    def get_altimeter(self):
        return str(self.data["current"]["pressure"])

    def get_visibility(self):
        #print("visibility", self.data["current"]["visibility"])
        return str(self.data["current"]["visibility"])

    def get_wind_speed(self):
        return float(self.data["current"]["wind_speed"])

    def get_wind_speed_kmh(self):
        kmh = self.get_wind_speed() * 3.6
        return math.floor(kmh * 100) / 100

    def get_wind_speed_knots(self):
        knots = self.get_wind_speed() * 1.94384
        return math.floor(knots * 100) / 100

    def get_wind_dir_degrees(self):
        return float(self.data["current"]["wind_deg"])

    def get_wind_dir_cardinal(self):
        return self.convert_wind_dir_degrees_to_cardinal_direction(float(self.data["current"]["wind_deg"]))

    def convert_wind_dir_degrees_to_cardinal_direction(self, wind_dir_degrees):
        directions = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
        index = int((wind_dir_degrees / 45) + 0.5)
        return directions[index % 8]
