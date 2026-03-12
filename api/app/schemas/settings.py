from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from pathlib import Path
from typing import Dict, Optional, Any
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


class CameraConfigGPS(BaseModel):
    lat: Optional[str] = None
    lon: Optional[str] = None
    rel_alt: Optional[str] = None
    alt: Optional[str] = None


class CameraConfigIR(BaseModel):
    ir: Optional[str] = None
    ir_value: Optional[str] = None
    ir_image_width: Optional[int] = None
    ir_image_height: Optional[int] = None
    ir_filename_pattern: Optional[str] = None
    ir_scale: Optional[float] = None


class CameraConfigCameraProperties(BaseModel):
    focal_length: Optional[str] = None
    fov: Optional[str] = None


class CameraConfigOrientation(BaseModel):
    cam_roll: Optional[str] = None
    cam_yaw: Optional[str] = None
    cam_pitch: Optional[str] = None
    uav_roll: Optional[str] = None
    uav_yaw: Optional[str] = None
    uav_pitch: Optional[str] = None


class CameraConfig(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    model_name: str = Field(alias="_model")
    auto_discovered: bool = Field(default=False, alias="_auto_discovered")

    created_at: Optional[str] = None
    width: Optional[str] = None
    height: Optional[str] = None
    projection_type: Optional[str] = None

    gps: CameraConfigGPS = Field(default_factory=CameraConfigGPS)
    ir: CameraConfigIR = Field(default_factory=CameraConfigIR)
    camera_properties: CameraConfigCameraProperties = Field(
        default_factory=CameraConfigCameraProperties
    )
    orientation: CameraConfigOrientation = Field(
        default_factory=CameraConfigOrientation
    )

    fov_correction: float = 1.0
    adjust_data: bool = False
    rgb_orientation_offset: Optional[Dict[str, Any]] = None
    fallbacks: Dict[str, Any] = Field(default_factory=lambda: {"thermal": {}})


class CameraConfigSummary(BaseModel):
    model_name: str
    auto_discovered: bool
    filename: str


class CreateCameraConfigBody(BaseModel):
    model_name: str
    exif_dump: Optional[Dict[str, Any]] = None
    initial_data: Optional[Dict[str, Any]] = None