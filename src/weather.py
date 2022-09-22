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

    def get_temperature(self):
        return self.data["current"]["temp"]
    
    def get_humidity(self):
        return str(self.data["current"]["humidity"])
    
    def get_altimeter(self):
        return str(self.data["current"]["pressure"])
        
    def get_wind_speed(self):
        return float(self.data["current"]["wind_speed"])
            
    def get_visibility(self):
        #print("visibility", self.data["current"]["visibility"])
        return str(self.data["current"]["visibility"])
    
    def get_wind_dir_degrees(self):
        return float(self.data["current"]["wind_deg"]) 
