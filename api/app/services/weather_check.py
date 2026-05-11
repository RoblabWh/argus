import logging
import requests

logger = logging.getLogger(__name__)


def try_openweather_key(api_key: str, timeout: float = 5.0) -> tuple[bool, str, str | None]:
    """
    Validate an OpenWeather API key with a cheap call to the current-weather
    endpoint at a fixed coordinate.
    Returns (success, message, detail). Does not read or write config.
    """
    if not api_key:
        return False, "OpenWeather API key is empty", None

    url = (
        "https://api.openweathermap.org/data/2.5/weather"
        f"?lat=0&lon=0&appid={api_key}&units=metric"
    )
    try:
        response = requests.get(url, timeout=timeout)
    except requests.exceptions.Timeout:
        return False, f"Connection timed out after {timeout}s", "timeout"
    except requests.exceptions.ConnectionError as e:
        return False, "Could not connect to OpenWeather", str(e)
    except requests.exceptions.RequestException as e:
        return False, "Request failed", str(e)

    if response.status_code == 200:
        return True, "API key is valid", None
    if response.status_code == 401:
        return False, "OpenWeather rejected the API key", "HTTP 401"
    return False, f"Unexpected response from OpenWeather (HTTP {response.status_code})", response.text[:200]
