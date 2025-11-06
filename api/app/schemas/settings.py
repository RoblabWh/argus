from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from pathlib import Path
from typing import Dict
import os


class WebODMSettings(BaseModel):
    ENABLE_WEBODM: bool
    WEBODM_URL: str
    WEBODM_USERNAME: str
    WEBODM_PASSWORD: str


class OpenWeatherSettings(BaseModel):
    OPEN_WEATHER_API_KEY: str


class DRZSettings(BaseModel):
    BACKEND_URL: str
    AUTHOR_NAME: str
    BACKEND_USERNAME: str
    BACKEND_PASSWORD: str


class AppearanceSettings(BaseModel):
    DETECTION_COLORS: Dict[str, str]  # e.g. {"fire":"#ff0000", "vehicle":"#00ff00"}