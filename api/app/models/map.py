from sqlalchemy import Column, Integer, String, DateTime, Boolean, Float, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from app.database import Base

# Define the 
# - Map and
# - MapElement 
# classes to represent the maps and their elements in the database.


class Map(Base):
    __tablename__ = "maps"

    id = Column(Integer, primary_key=True, index=True)
    mapping_report_id = Column(Integer, ForeignKey("mapping_reports.id"), index=True)
    name = Column(String)
    url = Column(String, nullable=True)
    created_at = Column(DateTime, nullable=True)
    odm = Column(Boolean, default=False)
    bounds = Column(JSONB, nullable=True)  # JSONB for storing bounds coordinates

    # relationships
    mapping_report = relationship("MappingReport", back_populates="maps")
    map_elements = relationship("MapElement", back_populates="map", cascade="all, delete")



class MapElement(Base):
    __tablename__ = "map_elements"

    id = Column(Integer, primary_key=True, index=True)
    map_id = Column(Integer, ForeignKey("maps.id"), index=True)
    image_id = Column(Integer, ForeignKey("images.id"))
    index = Column(Integer)
    coord = Column(JSONB)
    corners = Column(JSONB)
    px_coord = Column(JSONB)
    px_corners = Column(JSONB)

    # relationships
    map = relationship("Map", back_populates="map_elements")
    image = relationship("Image", back_populates="map_elements")
