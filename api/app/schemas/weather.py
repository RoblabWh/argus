from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


##################
## Weather
##################

class WeatherBase(BaseModel):
    report_id: int
    coord: Optional[dict] = None  # JSONB as dict
    temperature: Optional[float] = None
    humidity: Optional[float] = None
    air_pressure: Optional[float] = None
    wind_speed: Optional[float] = None
    wind_dir_deg: Optional[float] = None
    visibility: Optional[float] = None
    cloud_cover: Optional[float] = None
    weather_condition: Optional[str] = None  # e.g., "Clear", "Rain", "Snow"
    timestamp: Optional[datetime] = None

class WeatherCreate(WeatherBase):
    pass    

class WeatherUpdate(BaseModel):
    report_id: Optional[int] = None
    coord: Optional[dict] = None  # JSONB as dict
    temperature: Optional[float] = None
    humidity: Optional[float] = None
    air_pressure: Optional[float] = None
    wind_speed: Optional[float] = None
    wind_dir_deg: Optional[float] = None
    visibility: Optional[float] = None
    cloud_cover: Optional[float] = None
    weather_condition: Optional[str] = None  # e.g., "Clear", "Rain", "Snow"
    timestamp: Optional[datetime] = None

class WeatherOut(WeatherBase):
    id: int

    class Config:
        orm_mode = True