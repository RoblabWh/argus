import numpy as np
from app.services.thermal.thermal_parser.thermal import Thermal


def parse_thermal_image(filepath_image: str) -> np.ndarray:
    """
    Parses a thermal image and returns the temperature data.

    :param filepath_image: Path to the thermal image file.
    :return: Numpy array containing temperature data.
    """
    print(f"Parsing thermal image from {filepath_image}")
    thermal = Thermal(dtype=np.float32)
    return thermal.parse(filepath_image=filepath_image)
    
