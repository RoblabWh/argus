import numpy as np
from app.services.thermal.thermal_parser.thermal import Thermal
import os

thermal = Thermal(dtype=np.float32)

def parse_thermal_image(filepath_image: str) -> np.ndarray:
    """
    Parses a thermal image and returns the temperature data.

    :param filepath_image: Path to the thermal image file.
    :return: Numpy array containing temperature data.
    """
    #print(f"Parsing thermal image from {filepath_image}")    
    temp = thermal.parse(filepath_image=filepath_image)
    min_temp = temp.min()
    max_temp = temp.max()
    #print(f"Parsed thermal image with min_temp: {min_temp}, max_temp: {max_temp}")

    return temp, min_temp, max_temp


def save_as_temperature_matrix(thermal_image: np.ndarray, filepath: str) -> None:
    """
    Saves the thermal image as a temperature matrix in a .npy file.

    :param thermal_image: Numpy array containing the thermal image data.
    :param filepath: Path where the .npy file will be saved.
    """
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    #print(f"Saving thermal image to {filepath}")
    np.save(filepath, thermal_image)
    #print(f"Thermal image saved successfully to {filepath}")


def load_temperature_matrix(filepath: str) -> np.ndarray:
    """
    Loads a temperature matrix from a .npy file.

    :param filepath: Path to the .npy file.
    :return: Numpy array containing the thermal image data.
    """
    #print(f"Loading thermal image from {filepath}")
    thermal_image = np.load(filepath)
    #print(f"Thermal image loaded successfully from {filepath}")
    
    return thermal_image


def get_temperature_range(thermal_image: np.ndarray) -> tuple:
    """
    Gets the minimum and maximum temperature from a thermal image.

    :param thermal_image: Numpy array containing the thermal image data.
    :return: Tuple containing (min_temp, max_temp).
    """
    min_temp = thermal_image.min()
    max_temp = thermal_image.max()
    #print(f"Temperature range: min_temp={min_temp}, max_temp={max_temp}")
    
    return min_temp, max_temp


def process_thermal_image(filepath_image: str, save_path: str) -> tuple:
    """
    Processes a thermal image by parsing it, saving it as a temperature matrix,
    and returning the temperature range.

    :param filepath_image: Path to the thermal image file.
    :param save_path: Path where the processed .npy file will be saved.
    :return: Tuple containing (min_temp, max_temp).
    """
    thermal_image, min_temp, max_temp = parse_thermal_image(filepath_image)
    save_as_temperature_matrix(thermal_image, save_path)

    return min_temp, max_temp
