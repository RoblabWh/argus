import logging

from fastapi import APIRouter, Query
from geopy.exc import GeocoderServiceError, GeocoderTimedOut, GeocoderUnavailable
from geopy.geocoders import Nominatim
from pydantic import BaseModel

router = APIRouter(prefix="/geocode", tags=["Geocode"])
logger = logging.getLogger(__name__)

# Nominatim asks for an identifying user agent; keep it descriptive.
USER_AGENT = "argus-uav-recon"
TIMEOUT = 8


class GeocodeResult(BaseModel):
    display_name: str
    lat: float
    lon: float


def _geolocator() -> Nominatim:
    return Nominatim(user_agent=USER_AGENT, timeout=TIMEOUT)


@router.get("/search", response_model=list[GeocodeResult])
def search(
    q: str = Query(..., min_length=3, description="Address or place name"),
    limit: int = Query(5, ge=1, le=10),
):
    """
    Forward-geocode an address to coordinates.

    Missions are often run on sites without internet, so an unreachable geocoder is a
    normal condition, not an error: it degrades to an empty result list and the user
    picks the coordinate on the map by hand instead.
    """
    try:
        locations = _geolocator().geocode(q, exactly_one=False, limit=limit)
    except (GeocoderUnavailable, GeocoderTimedOut, GeocoderServiceError) as e:
        logger.warning(f"Geocoder unavailable for query '{q}': {e}")
        return []
    except Exception as e:
        logger.error(f"Geocoding failed for query '{q}': {e}")
        return []

    if not locations:
        return []

    return [
        GeocodeResult(display_name=loc.address, lat=loc.latitude, lon=loc.longitude)
        for loc in locations
    ]


@router.get("/reverse", response_model=GeocodeResult | None)
def reverse(lat: float = Query(...), lon: float = Query(...)):
    """Reverse-geocode coordinates to an address, or null if unavailable."""
    try:
        location = _geolocator().reverse(f"{lat}, {lon}")
    except (GeocoderUnavailable, GeocoderTimedOut, GeocoderServiceError) as e:
        logger.warning(f"Reverse geocoder unavailable for ({lat}, {lon}): {e}")
        return None
    except Exception as e:
        logger.error(f"Reverse geocoding failed for ({lat}, {lon}): {e}")
        return None

    if not location:
        return None
    return GeocodeResult(display_name=location.address, lat=location.latitude, lon=location.longitude)
