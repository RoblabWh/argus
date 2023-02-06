#!/usr/bin/env python3
__author__      = "Artur Leinweber"
__copyright__ = "Copyright 2020"
__credits__ = ["None"]
__license__ = "GPL"
__version__ = "1.0.1"
__maintainer__ = "Artur Leinweber"
__email__ = "arturleinweber@live.de"
__status__ = "Production"

from abc import ABC, abstractmethod

class Optimizer(ABC):

    def __init__(self):
        super().__init__()
   
    @abstractmethod
    def optimize(self):
        pass
        
