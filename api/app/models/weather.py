from sqlalchemy import Column, Integer, String, DateTime, Boolean, Float, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from app.database import Base


class Weather(Base):
    __tablename__ = "weather"

    id = Column(Integer, primary_key=True, index=True)
    mapping_report_id = Column(Integer, ForeignKey("mapping_reports.id"), index=True)
    open_weather_id = Column(String, nullable=True)  # OpenWeatherMap ID for the location
    description = Column(String, nullable=True)  # Weather description (e.g., "clear sky", "light rain")
    temperature = Column(Float, nullable=True)
    humidity = Column(Float, nullable=True)
    pressure = Column(Float, nullable=True)
    wind_speed = Column(Float, nullable=True)
    wind_dir_deg = Column(Float, nullable=True)
    visibility = Column(Float, nullable=True)
    timestamp = Column(DateTime, nullable=True)

    # relationships
    mapping_report = relationship("MappingReport", back_populates="weather")
