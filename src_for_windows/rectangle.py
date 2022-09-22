#!/usr/bin/env python3
__author__      = "Artur Leinweber"
__copyright__ = "Copyright 2020"
__credits__ = ["None"]
__license__ = "GPL"
__version__ = "1.0.1"
__maintainer__ = "Artur Leinweber"
__email__ = "arturleinweber@live.de"
__status__ = "Production"

import shapely.geometry
import shapely.affinity
from shapely.geometry import MultiPoint


class RotatedRect:
    def __init__(self, cx, cy, w, h, angle):
        self.cx = cx
        self.cy = cy
        self.w = w
        self.h = h
        self.angle = angle

    def get_contour(self):
        w = self.w
        h = self.h
        c = shapely.geometry.box(int(-w/2.0), int(-h/2.0), int(w/2.0), int(h/2.0))
        rc = shapely.affinity.rotate(c, self.angle)
        return shapely.affinity.translate(rc, self.cx, self.cy)

    def get_center(self):
        return (int(self.cx), int(self.cy))

    def set_center(self, coordinate):
        self.cx, self.cy = coordinate

    def set_angle(self, angle):
        self.angle = angle

    def get_size(self):
        return (self.w, self.h)
    
    def set_size(self, size):
        w, h = size
        self.w = w
        self.h = h 

    def get_shape(self):
        (minx, miny, maxx, maxy) = MultiPoint(self.get_contour().exterior.coords[:]).bounds
        return (maxy-miny, maxx-minx)

    def get_bounds(self):
        (minx, miny, maxx, maxy) = MultiPoint(self.get_contour().exterior.coords[:]).bounds
        return (minx, miny, maxx, maxy)

    def get_angle(self):
        return self.angle

    def get_multipoint(self):
        return MultiPoint(self.get_contour().exterior.coords[:])
