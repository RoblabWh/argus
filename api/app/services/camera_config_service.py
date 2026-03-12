import json
import shutil
import tempfile
from pathlib import Path
from fastapi import UploadFile

from app.services.image_metadata_extraction import (
    CAMERA_CONFIGS_DIR,
    _model_name_to_filename,
    _read_metadata,
)


def list_configs() -> list[dict]:
    """Return summary of all model configs, excluding _default and other templates."""
    results = []
    for path in sorted(CAMERA_CONFIGS_DIR.glob("*.json")):
        if path.name.startswith("_"):
            continue
        with path.open() as f:
            data = json.load(f)
        results.append({
            "model_name": data.get("_model", path.stem),
            "auto_discovered": data.get("_auto_discovered", False),
            "filename": path.name,
        })
    return results


def get_config(model_name: str) -> dict | None:
    """Load config for model_name, or None if not found."""
    path = CAMERA_CONFIGS_DIR / _model_name_to_filename(model_name)
    if not path.exists():
        return None
    with path.open() as f:
        return json.load(f)


def save_config(model_name: str, config_data: dict) -> None:
    """Write config dict to disk."""
    path = CAMERA_CONFIGS_DIR / _model_name_to_filename(model_name)
    CAMERA_CONFIGS_DIR.mkdir(exist_ok=True)
    with path.open("w") as f:
        json.dump(config_data, f, indent=2)


def build_empty_config(model_name: str) -> dict:
    """Return an empty config structure with all EXIF key fields set to None."""
    return {
        "_model": model_name,
        "_auto_discovered": False,
        "created_at": None,
        "width": None,
        "height": None,
        "projection_type": None,
        "gps": {"lat": None, "lon": None, "rel_alt": None, "alt": None},
        "ir": {},
        "camera_properties": {"focal_length": None, "fov": None},
        "orientation": {
            "cam_roll": None, "cam_yaw": None, "cam_pitch": None,
            "uav_roll": None, "uav_yaw": None, "uav_pitch": None,
        },
        "fov_correction": 1.0,
        "adjust_data": False,
        "fallbacks": {"thermal": {}},
    }


def read_exif_from_upload_sync(file: UploadFile) -> dict:
    """Save UploadFile to temp, run pyexifinfo, delete temp. Returns raw metadata dict."""
    suffix = Path(file.filename).suffix if file.filename else ".jpg"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp_path = tmp.name
    try:
        with open(tmp_path, "wb") as f:
            shutil.copyfileobj(file.file, f)
        return _read_metadata(tmp_path)
    finally:
        Path(tmp_path).unlink(missing_ok=True)
