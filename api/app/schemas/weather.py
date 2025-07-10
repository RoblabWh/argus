from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


##################
## Weather
##################

class WeatherBase(BaseModel):
    mapping_report_id: int
    open_weather_id: Optional[str] = None  # OpenWeatherMap ID for the location
    description: Optional[str] = None  # Weather description (e.g., "clear sky
    temperature: Optional[float] = None
    humidity: Optional[float] = None
    pressure: Optional[float] = None
    wind_speed: Optional[float] = None
    wind_dir_deg: Optional[float] = None
    visibility: Optional[float] = None
    timestamp: Optional[datetime] = None

class WeatherCreate(WeatherBase):
    pass    

class WeatherUpdate(BaseModel):
    mapping_report_id: Optional[int] = None
    open_weather_id: Optional[str] = None
    description: Optional[str] = None  # Weather description (e.g., "clear sky
    temperature: Optional[float] = None
    humidity: Optional[float] = None
    pressure: Optional[float] = None
    wind_speed: Optional[float] = None
    wind_dir_deg: Optional[float] = None
    visibility: Optional[float] = None
    timestamp: Optional[datetime] = None

class WeatherOut(WeatherBase):
    id: int

    class Config:
        orm_mode = True