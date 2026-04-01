import json
import logging
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from fastapi import UploadFile

logger = logging.getLogger(__name__)

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





def extract_video_metadata(video_path: str) -> tuple:
    """Extract flight_timestamp (oldest valid date) and camera_model from video via exiftool."""
    DATE_FIELDS = [
        "QuickTime:CreateDate", "QuickTime:MediaCreateDate", "QuickTime:TrackCreateDate",
        "EXIF:DateTimeOriginal", "EXIF:CreateDate",
        "File:FileCreateDate", "File:FileModifyDate",
    ]
    CAMERA_FIELDS = ["XMP:StitchingSoftware", "QuickTime:Make", "EXIF:Model"]
    logger.info(f"Extracting video metadata from {video_path}")
    metadata = None
    try:
        metadata = _read_metadata(video_path)
    except Exception:
        logger.warning(f"pyexifinfo failed on {video_path}", exc_info=True)
        return None, "N/A"

    # --- flight_timestamp: collect all dates, filter bad ones, pick oldest ---
    now_utc = datetime.now(timezone.utc)
    candidates = []
    for field in DATE_FIELDS:
        raw_val = None
        try:
            raw_val = metadata.get(field)
        except Exception:
            continue
            
        if not raw_val:
            continue
        raw_str = str(raw_val).strip()
        if not raw_str or "0000:00:00" in raw_str:
            continue
        try:
            # Convert exiftool "YYYY:MM:DD HH:MM:SS[±HH:MM]" → ISO8601
            iso_str = raw_str[:10].replace(":", "-") + "T" + raw_str[11:]
            dt = datetime.fromisoformat(iso_str)
        except (ValueError, IndexError):
            logger.info(f"Could not parse date field {field}: {raw_str!r}")
            continue
        dt_utc = dt.astimezone(timezone.utc) if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        # Skip if it looks like a file-copy timestamp (within 20 s of now)
        if abs((now_utc - dt_utc).total_seconds()) < 20:
            continue
        candidates.append(dt_utc)

    flight_timestamp = min(candidates).replace(tzinfo=None) if candidates else None

    # --- camera_model: first non-empty candidate ---
    camera_model = "N/A"
    for field in CAMERA_FIELDS:
        val = None
        try:
            val = metadata.get(field)
        except Exception:
            continue
        if val and str(val).strip():
            camera_model = str(val).strip()
            break

    return flight_timestamp, camera_model

