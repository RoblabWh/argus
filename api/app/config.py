import os
from pathlib import Path

DATABASE_URL = os.getenv("DATABASE_URL")
REDIS_PORT = os.getenv("REDIS_PORT", 6379)
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
UPLOAD_DIR = Path("reports_data")
OPEN_WEATHER_API_KEY = os.getenv("OPEN_WEATHER_API_KEY")
WEBODM_ENABLED = os.getenv("WEBODM_ENABLED", "false").lower() == "true"
WEBODM_USERNAME = os.getenv("WEBODM_USERNAME", "admin")
WEBODM_PASSWORD = os.getenv("WEBODM_PASSWORD", "admin")
WEBODM_URL = os.getenv("WEBODM_URL", "http://127.0.0.1:8000")
