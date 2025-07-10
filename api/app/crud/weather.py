from sqlalchemy.orm import Session, joinedload
from datetime import datetime
import redis

from app import models
from app.schemas.weather import WeatherCreate, WeatherUpdate

def get_all_weather_data(db: Session):
    """
    Get all weather data from the database.
    """
    return db.query(models.Weather).all()

def get_weather_data_by_mapping_report_id(db: Session, mapping_report_id: int):
    """
    Get weather data for a specific mapping report by its ID.
    """
    try:
        return (
            db.query(models.Weather)
            .filter(models.Weather.mapping_report_id == mapping_report_id)
            .options(joinedload(models.Weather.mapping_report))
            .first()
        )
    except Exception as e:
        print(f"Error fetching weather data: {e}")
        return None

def create_weather_data(db: Session, mapping_report_id: int, data: WeatherCreate):
    """Create new weather data for a mapping report."""
    new_weather = models.Weather(
        **data.dict(),
    )
    db.add(new_weather)
    db.commit()
    db.refresh(new_weather)
    return new_weather

def update_weather_data(db: Session, weather_id: int, update_data: WeatherUpdate):
    """
    Update existing weather data by its ID.
    """
    weather = db.query(models.Weather).filter(models.Weather.id == weather_id).first()
    if not weather:
        return None

    for key, value in update_data.dict(exclude_unset=True).items():
        setattr(weather, key, value)

    weather.timestamp = datetime.utcnow()
    db.commit()
    db.refresh(weather)
    return weather
