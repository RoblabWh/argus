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
    def __init__(self, lat, lon, timestamp, default, api_key=None):
        """
        Constructor
        """
        self.default = self.unshuffle(default)
        self.api_key = api_key if api_key is not None else self.default
        self.timestamp = timestamp
        self.default_url = self.build_url(lat, lon, self.default)
        self.url = self.build_url(lat, lon, self.api_key, timestamp=self.timestamp)
        print("URL:", self.url, flush=True)
        print("Default URL:", self.default_url, flush=True)
        try:
            if self.api_key is None:
                raise Exception("No API key provided, falling back to default key")
            self.data = self.get_data(self.url)
            print("Data loaded with timestamp:", self.timestamp , self.data, flush=True)

            if self.data["cod"] == 401 or self.data["cod"] == "401":
                raise Exception("API key invalid, falling back to default key")
            if self.data["cod"] == 400 or self.data["cod"] == "400":
                raise Exception("Bad request, falling back to default key (timestamp too old or out of range of key)")
        except Exception as e:
            print(e)
            self.data = self.get_data(self.default_url)
            print("Data loaded with default key", self.data, flush=True)


    def build_url(self, lat, lon, key, timestamp=None):
        if timestamp is not None:
            return "https://api.openweathermap.org/data/2.5/onecall/timemachine?lat=%s&lon=%s&dt=%s&appid=%s&units=metric" % (lat, lon, timestamp, key)
        return     "https://api.openweathermap.org/data/2.5/weather?lat=%s&lon=%s&appid=%s&units=metric" % (lat, lon, key)

    def get_data(self, url):
        response = requests.get(url)
        return json.loads(response.text)

    def get_value(self, key):
        # check if the data has the key  if not, check wether it has the key "main" or "current" and then check if the key is in the main dict
        if key in self.data:
            return self.data[key]

        if "main" in self.data:
            if key in self.data["main"]:
                return self.data["main"][key]

        if "current" in self.data:
            if key in self.data["current"]:
                return self.data["current"][key]

        return "N/A"

    def get_wind_value(self, key):
        if "wind" in self.data:
            if key in self.data["wind"]:
                return self.data["wind"][key]

        key = "wind_" + key

        return self.get_value(key)


    def get_temperature(self):
        return self.get_value("temp")
    
    def get_humidity(self):
        return str(self.get_value("humidity"))
    
    def get_altimeter(self):
        return str(self.get_value("pressure"))

    def get_visibility(self):
        #print("visibility", self.data["current"]["visibility"])
        return str(self.get_value("visibility"))

    def get_wind_speed(self):
        return float(self.get_wind_value("speed"))

    def get_wind_speed_kmh(self):
        kmh = self.get_wind_speed() * 3.6
        return math.floor(kmh * 100) / 100

    def get_wind_speed_knots(self):
        knots = self.get_wind_speed() * 1.94384
        return math.floor(knots * 100) / 100

    def get_wind_dir_degrees(self):
        return float(self.get_wind_value("deg"))

    def get_wind_dir_cardinal(self):
        return self.convert_wind_dir_degrees_to_cardinal_direction(self.get_wind_dir_degrees())

    def convert_wind_dir_degrees_to_cardinal_direction(self, wind_dir_degrees):
        directions = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
        index = int((wind_dir_degrees / 45) + 0.5)
        return directions[index % 8]

    def generate_weather_dict(self):


        temperature = self.get_temperature()
        print("Temperature:", temperature, flush=True)
        humidity = self.get_humidity()
        print("Humidity:", humidity, flush=True)
        altimeter = self.get_altimeter()
        print("Altimeter:", altimeter, flush=True)
        wind_speed_ms = self.get_wind_speed()
        print("Wind Speed (m/s):", wind_speed_ms, flush=True)
        wind_speed_kmh = self.get_wind_speed_kmh()
        print("Wind Speed (km/h):", wind_speed_kmh, flush=True)
        wind_speed_knots = self.get_wind_speed_knots()
        print("Wind Speed (knots):", wind_speed_knots, flush=True)
        visibility = self.get_visibility()
        print("Visibility:", visibility, flush=True)
        wind_dir_degrees = self.get_wind_dir_degrees()
        print("Wind Direction (degrees):", wind_dir_degrees, flush=True)
        wind_dir_cardinal = self.get_wind_dir_cardinal()
        print("Wind Direction (cardinal):", wind_dir_cardinal, flush=True)


        weather_data = []
        weather_data.append({"description": 'Temperature', "value": str(temperature) + "°C"})
        weather_data.append({"description": 'Humidity', "value": str(humidity) + "%"})
        weather_data.append({"description": 'Air Preasure', "value": str(altimeter) + "hPa"})
        weather_data.append({"description": 'Wind Speed',
                             "value": str(wind_speed_ms) + "m/s" + " (" + str(wind_speed_kmh) + "km/h, " + str(
                                 wind_speed_knots) + "knots)"})
        weather_data.append(
            {"description": 'Wind Direction', "value": str(wind_dir_degrees) + "°  (" + str(wind_dir_cardinal) + ")"})
        weather_data.append({"description": 'Visibility', "value": str(visibility) + "m"})

        return weather_data

    def unshuffle(self, k):
        k_b = k[::-1]
        k = '3' + k_b
        return k
