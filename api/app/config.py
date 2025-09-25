# import os
# from pathlib import Path
# import json
# import logging
# logger = logging.getLogger(__name__)


# # Path to the .env file mounted from base folder
# ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
# CONFIG_PATH = Path(__file__).resolve().parent / "config.json"

# def load_local_settings() -> dict:
#     logger.info(f"Loading local settings from {CONFIG_PATH}")
#     with open(CONFIG_PATH) as f:
#         loaded_data = json.load(f)
#         return loaded_data
#     return {}

# def write_local_settings(settings: dict):
#     logger.info(f"Writing local settings to {CONFIG_PATH}")
#     current = load_local_settings()
#     current.update(settings)
#     with open(CONFIG_PATH, "w") as f:
#         json.dump(current, f, indent=4)

# def read_env_file(path: str) -> dict:
#     env_vars = {}
#     logger.info(f"Reading .env file from {path}")
#     if not os.path.exists(path):
#         logger.warning(f".env file not found at {path}")
#         return env_vars
#     with open(path, "r") as f:
#         for line in f:
#             line = line.strip()
#             # skip empty lines or comments
#             if not line or line.startswith("#"):
#                 continue

#             if "=" in line:
#                 key, value = line.split("=", 1)  # only split at the first "="
#                 # remove optional surrounding quotes
#                 value = value.strip().strip('"').strip("'")
#                 env_vars[key.strip()] = value
#     logger.info(f"Loaded env vars: {env_vars}")
#     return env_vars

# def write_env(updates: dict):
#     """Merge updates into the .env file (preserve other keys)."""
#     logger.info(f"Writing updated .env to {ENV_PATH}")
#     current = read_env_file(ENV_PATH)
#     current.update(updates)
#     with ENV_PATH.open("w") as f:
#         for key, value in current.items():
#             f.write(f'{key}="{value}"\n')

# LOCAL_SETTINGS = load_local_settings()


# DATABASE_URL = os.getenv("DATABASE_URL")
# REDIS_PORT = os.getenv("REDIS_PORT", 6379)
# REDIS_HOST = os.getenv("REDIS_HOST", "redis")
# UPLOAD_DIR = Path("reports_data")
# OPEN_WEATHER_API_KEY = os.getenv("OPEN_WEATHER_API_KEY")
# WEBODM_ENABLED = os.getenv("WEBODM_ENABLED", "false").lower() == "true"
# WEBODM_USERNAME = os.getenv("WEBODM_USERNAME", "admin")
# WEBODM_PASSWORD = os.getenv("WEBODM_PASSWORD", "admin")
# WEBODM_URL = os.getenv("WEBODM_URL", "http://127.0.0.1:8000")
# DRZ_BACKEND_URL = LOCAL_SETTINGS.get("DRZ_BACKEND_URL", "")
# DRZ_AUTHOR_NAME = LOCAL_SETTINGS.get("DRZ_AUTHOR_NAME", "")
# DETECTION_COLORS = LOCAL_SETTINGS.get("DETECTION_COLORS", {})


import os
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class Config:

    def __init__(self):
        # file paths
        self.env_path = Path(__file__).resolve().parent.parent / ".env"
        self.config_path = Path(__file__).resolve().parent / "config.json"

        # runtime storage
        self._env_vars: dict = {}
        self._local_settings: dict = {}

        # initial load
        self.refresh()

    
    def _read_env_file(self) -> dict:
        env_vars = {}
        logger.info(f"Reading .env file from {self.env_path}")
        if not self.env_path.exists():
            logger.warning(f".env file not found at {self.env_path}")
            return env_vars
        with self.env_path.open("r") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, value = line.split("=", 1)
                    env_vars[key.strip()] = value.strip().strip('"').strip("'")
        return env_vars

    def _load_local_settings(self) -> dict:
        logger.info(f"Loading local settings from {self.config_path}")
        if not self.config_path.exists():
            logger.warning(f"config.json not found at {self.config_path}")
            return {}
        with self.config_path.open() as f:
            return json.load(f)

    def write_local_settings(self, settings: dict):
        """Update config.json with new settings."""
        logger.info(f"Writing local settings to {self.config_path}")
        current = self._load_local_settings()
        current.update(settings)
        with self.config_path.open("w") as f:
            json.dump(current, f, indent=4)
        self._local_settings = current
        self._set_variables_local()

    def write_env(self, updates: dict):
        """Merge updates into the .env file and keep others intact."""
        logger.info(f"Writing updated .env to {self.env_path}")
        current = self._read_env_file()
        current.update(updates)
        with self.env_path.open("w") as f:
            for key, value in current.items():
                f.write(f'{key}={value}\n')
        self._env_vars = current
        logger.info(f"Updated environment variables: {self._env_vars}")
        self._set_variables_env()

    
    def refresh(self):
        """
        Reload both .env and config.json into memory
        and update all public attributes.
        """
        logger.info("Refreshing configuration from .env and config.json")
        self._env_vars = self._read_env_file()
        self._local_settings = self._load_local_settings()

        self._set_variables_local()
        self._set_variables_env()


    def _set_variables_env(self):
        self.DATABASE_URL = self._get_env("DATABASE_URL")
        self.REDIS_PORT = int(self._get_env("REDIS_PORT", 6379))
        self.REDIS_HOST = self._get_env("REDIS_HOST", "redis")
        self.UPLOAD_DIR = Path("reports_data")
        self.OPEN_WEATHER_API_KEY = self._get_env("OPEN_WEATHER_API_KEY")
        self.WEBODM_ENABLED = self._get_env("ENABLE_WEBODM", "false").lower() == "true"
        self.WEBODM_USERNAME = self._get_env("WEBODM_USERNAME", "admin")
        self.WEBODM_PASSWORD = self._get_env("WEBODM_PASSWORD", "admin")
        self.WEBODM_URL = self._get_env("WEBODM_URL", "http://127.0.0.1:8000")

    def _set_variables_local(self):        
        # Local config.json settings
        self.DRZ_BACKEND_URL = self._local_settings.get("DRZ_BACKEND_URL", "")
        self.DRZ_AUTHOR_NAME = self._local_settings.get("DRZ_AUTHOR_NAME", "")
        self.DETECTION_COLORS = self._local_settings.get("DETECTION_COLORS", {})

    def _get_env(self, key: str, default=None):
        """Lookup key in os.environ first, then .env file, then default."""
        #return os.getenv(key, self._env_vars.get(key, default))
        return  self._env_vars.get(key, default)

    # Convenience accessors
    @property
    def env_vars(self) -> dict:
        return dict(self._env_vars)

    @property
    def local_settings(self) -> dict:
        return dict(self._local_settings)


# create a global singleton instance
config = Config()
