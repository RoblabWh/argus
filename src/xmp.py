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


class XMP:
    def __init__(self, flight_yaw_degree, flight_pitch_degree, flight_roll_degree, gimbal_yaw_degree, gimbal_pitch_degree, gimbal_roll_degree):
        """
        Constructor
        """
        self.flight_yaw_degree = flight_yaw_degree
        self.flight_pitch_degree = flight_pitch_degree
        self.flight_roll_degree = flight_roll_degree
        self.gimbal_yaw_degree = gimbal_yaw_degree
        self.gimbal_pitch_degree = gimbal_pitch_degree
        self.gimbal_roll_degree = gimbal_roll_degree

    def __str__(self):
        """
        Represent the string interpretation of XMP values.
        :return: string representation
        """
        return "FlightYawDegree: " + str(self.flight_yaw_degree) + "\n" \
               + "FlightPitchDegree: " + str(self.flight_pitch_degree) + "\n" \
               + "FlightRollDegree: " + str(self.flight_roll_degree) + "\n" \
               + "GimbalYawDegree: " + str(self.gimbal_yaw_degree) + "\n" \
               + "GimbalPitchDegree: " + str(self.gimbal_pitch_degree) + "\n" \
               + "GimbalRollDegree: " + str(self.gimbal_roll_degree) + "\n"

    def get_flight_yaw_degree(self):
        """
        Returning flight_yaw_degree.
        :return: flight_yaw_degree
        """
        return self.flight_yaw_degree

    def get_flight_pitch_degree(self):
        """
        Returning flight_pitch_degree.
        :return: flight_pitch_degree
        """
        return self.flight_pitch_degree

    def get_flight_roll_degree(self):
        """
        Returning flight_roll_degree.
        :return: flight_roll_degree
        """
        return self.flight_roll_degree

    def get_gimbal_yaw_degree(self):
        """
        Returning gimbal_yaw_degree.
        :return: gimbal_yaw_degree
        """
        return self.gimbal_yaw_degree

    def get_gimbal_pitch_degree(self):
        """
        Returning gimbal_pitch_degree.
        :return: gimbal_pitch_degree
        """
        return self.gimbal_pitch_degree

    def get_gimbal_roll_degree(self):
        """
        Returning gimbal_roll_degree.
        :return: gimbal_roll_degree
        """
        return self.gimbal_roll_degree
