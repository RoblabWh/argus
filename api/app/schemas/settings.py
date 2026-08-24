from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator
from pathlib import Path
from typing import Dict, Optional, Any
import os
import re


class WebODMSettings(BaseModel):
    ENABLE_WEBODM: bool
    WEBODM_URL: str
    WEBODM_USERNAME: str
    WEBODM_PASSWORD: str


class OpenWeatherSettings(BaseModel):
    OPEN_WEATHER_API_KEY: str


class HuggingFaceSettings(BaseModel):
    HF_TOKEN: str


class DRZSettings(BaseModel):
    BACKEND_URL: str
    AUTHOR_NAME: str
    BACKEND_USERNAME: str
    BACKEND_PASSWORD: str


_HEX_COLOR = re.compile(r"#[0-9a-fA-F]{6}")

# The class list is user-editable in the settings page, so it is free-form —
# but bounded, since it all lands in a single config.json key.
MAX_DETECTION_COLORS = 200


class AppearanceSettings(BaseModel):
    # Detection class_name -> "#rrggbb". Free-form keys: class names come from
    # whichever detector produced them (e.g. "fire", "human", "land_vehicle").
    # Classes absent here get an automatic color assigned by the frontend.
    DETECTION_COLORS: Dict[str, str]

    @field_validator("DETECTION_COLORS")
    @classmethod
    def _validate_colors(cls, value: Dict[str, str]) -> Dict[str, str]:
        if len(value) > MAX_DETECTION_COLORS:
            raise ValueError(
                f"at most {MAX_DETECTION_COLORS} detection colors allowed, got {len(value)}"
            )
        cleaned: Dict[str, str] = {}
        for class_name, color in value.items():
            name = class_name.strip()
            if not name:
                raise ValueError("detection class names must not be empty")
            if not _HEX_COLOR.fullmatch(color):
                raise ValueError(
                    f"color for {name!r} must be a #rrggbb hex value, got {color!r}"
                )
            cleaned[name] = color.lower()
        return cleaned


class SettingsTestResult(BaseModel):
    success: bool
    message: str
    detail: Optional[str] = None
    latency_ms: Optional[int] = None


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