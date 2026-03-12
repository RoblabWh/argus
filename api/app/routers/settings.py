from fastapi import APIRouter, HTTPException, File, UploadFile
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel
from pathlib import Path
from typing import Dict, Any
import os
import logging
from app.config import config

from app.schemas.settings import (
    WebODMSettings,
    OpenWeatherSettings,
    DRZSettings,
    AppearanceSettings,
    CameraConfigSummary,
    CameraConfig,
    CreateCameraConfigBody,
)
import app.services.camera_config_service as camera_config_svc
from app.services.image_metadata_extraction import _auto_discover_config

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/settings", tags=["settings"])

# Path to the .env file mounted from base folder
ENV_PATH = Path(__file__).resolve().parent.parent.parent / ".env"


@router.get("/")
def get_all_settings():
    """
    Return all settings from the .env file and any DB-backed defaults.
    This is used to populate the frontend on page load.
    """
    logger.info("Fetching all settings")
    env_vars = config.env_vars
    local_vars = config.local_settings
    # logger.info(f"Env vars: {env_vars}")
    # logger.info(f"Local vars: {local_vars}")
    return {
        "OPEN_WEATHER_API_KEY": env_vars.get("OPEN_WEATHER_API_KEY", "no key set"),
        "ENABLE_WEBODM": env_vars.get("ENABLE_WEBODM", "false").lower() == "true",
        "WEBODM_URL": env_vars.get("WEBODM_URL", "http://127.0.0.1:8000"),
        "WEBODM_USERNAME": env_vars.get("WEBODM_USERNAME", ""),
        "WEBODM_PASSWORD": env_vars.get("WEBODM_PASSWORD", ""),
        "DRZ_BACKEND_URL": local_vars.get("DRZ_BACKEND_URL", ""),
        "DRZ_AUTHOR_NAME": local_vars.get("DRZ_AUTHOR_NAME", ""),
        "DRZ_BACKEND_USERNAME": local_vars.get("DRZ_BACKEND_USERNAME", ""),
        "DRZ_BACKEND_PASSWORD": local_vars.get("DRZ_BACKEND_PASSWORD", ""),
        "DETECTION_COLORS": local_vars.get("DETECTION_COLORS", {}),
    }


@router.put("/webodm")
def update_webodm(settings: WebODMSettings):
    logger.info(f"Updating WebODM settings: {settings}")
    try:
        config.write_env(
            {
                "ENABLE_WEBODM": str(settings.ENABLE_WEBODM).lower(),
                "WEBODM_URL": settings.WEBODM_URL,
                "WEBODM_USERNAME": settings.WEBODM_USERNAME,
                "WEBODM_PASSWORD": settings.WEBODM_PASSWORD,
            }
        )
        return {
            "message": "WebODM settings updated. Restart container to apply changes."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/openweather")
def update_openweather(settings: OpenWeatherSettings):
    logger.info(f"Updating OpenWeather settings: {settings}")
    try:
        config.write_env({"OPEN_WEATHER_API_KEY": settings.OPEN_WEATHER_API_KEY})
        return {
            "message": "OpenWeather API key updated. Restart container to apply changes."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/drz")
def update_drz(settings: DRZSettings):
    logger.info(f"Updating DRZ settings: {settings}")
    try:
        url = settings.BACKEND_URL
        if url:
            url = settings.BACKEND_URL if (settings.BACKEND_URL[-1] == "/" ) else settings.BACKEND_URL+"/" 
        config.write_local_settings(
            {
                "DRZ_BACKEND_URL": url,
                "DRZ_AUTHOR_NAME": settings.AUTHOR_NAME,
                "DRZ_BACKEND_USERNAME": settings.BACKEND_USERNAME,
                "DRZ_BACKEND_PASSWORD": settings.BACKEND_PASSWORD,
            }
        )
        return {"message": "DRZ settings updated."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    


@router.put("/appearance")
def update_appearance(settings: AppearanceSettings):
    """
    These might be frontend-only (not needed at container start).
    You can either write them into .env or store elsewhere (DB/file).
    """
    logger.info(f"Updating appearance settings: {settings}")
    try:
        # flatten detection colors into keys like COLOR_FIRE
        config.write_local_settings({"DETECTION_COLORS": settings.DETECTION_COLORS})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"message": "Appearance settings updated."}

@router.get("/appearance")
def get_appearance_settings():
    """
    Return appearance settings from the local config file.
    """
    logger.info("Fetching appearance settings")
    local_vars = config.local_settings
    return {
        "DETECTION_COLORS": local_vars.get("DETECTION_COLORS", {}),
    }


@router.post("/camera_configs/exif_dump")
async def get_exif_dump(file: UploadFile = File(...)) -> dict[str, Any]:
    """Upload a sample image; returns the complete pyexifinfo metadata dict (not saved)."""
    try:
        return await run_in_threadpool(camera_config_svc.read_exif_from_upload_sync, file)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.get("/camera_configs", response_model=list[CameraConfigSummary])
def list_camera_configs():
    """List all camera model configs (name, auto-discovered flag, filename)."""
    return camera_config_svc.list_configs()


@router.post("/camera_configs", status_code=201)
def create_camera_config(body: CreateCameraConfigBody) -> dict[str, Any]:
    """
    Create a new camera config.
    - If exif_dump is provided: auto-discover EXIF keys from that dump.
    - If exif_dump is null: create an empty config with all fields set to None.
    Returns 409 if a config for model_name already exists.
    """
    if camera_config_svc.get_config(body.model_name) is not None:
        raise HTTPException(
            status_code=409,
            detail=f"Config for '{body.model_name}' already exists. Use PUT to update.",
        )
    if body.exif_dump:
        config_data = _auto_discover_config(body.model_name, body.exif_dump)
    elif body.initial_data:
        config_data = body.initial_data
        config_data["_model"] = body.model_name
        camera_config_svc.save_config(body.model_name, config_data)
    else:
        config_data = camera_config_svc.build_empty_config(body.model_name)
        camera_config_svc.save_config(body.model_name, config_data)
    return config_data


@router.get("/camera_configs/{model_name}")
def get_camera_config(model_name: str) -> dict[str, Any]:
    """Return full config JSON for a camera model. 404 if not found."""
    data = camera_config_svc.get_config(model_name)
    if data is None:
        raise HTTPException(status_code=404, detail=f"Config for '{model_name}' not found.")
    return data


@router.put("/camera_configs/{model_name}")
def update_camera_config(model_name: str, config: CameraConfig) -> dict[str, Any]:
    """
    Save an updated config for a camera model.
    _model in the body is overridden by the URL path param (prevents renames).
    404 if the config doesn't exist yet (use POST to create).
    """
    if camera_config_svc.get_config(model_name) is None:
        raise HTTPException(status_code=404, detail=f"Config for '{model_name}' not found.")
    data = config.model_dump(by_alias=True, exclude_none=False)
    data["_model"] = model_name
    camera_config_svc.save_config(model_name, data)
    return data