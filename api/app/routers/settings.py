from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from pathlib import Path
from typing import Dict
import os
import logging
from app.config import config

from app.schemas.settings import (
    WebODMSettings,
    OpenWeatherSettings,
    DRZSettings,
    AppearanceSettings,
)

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
        config.write_local_settings(
            {
                "DRZ_BACKEND_URL": settings.BACKEND_URL,
                "DRZ_AUTHOR_NAME": settings.AUTHOR_NAME,
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