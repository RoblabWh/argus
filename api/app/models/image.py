from sqlalchemy import Column, Integer, String, DateTime, Boolean, Float, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from app.database import Base

# Defining the 
# - Image, 
# - MappingData, 
# - ThermalData, and
# - Detection
# classes for the database schema
# These classes represent the tables in the database and define their relationships


class Image(Base):
    __tablename__ = "images"

    id = Column(Integer, primary_key=True, index=True)
    mapping_report_id = Column(Integer, ForeignKey("mapping_reports.id"), index=True)
    filename = Column(String)
    url = Column(String)
    thumbnail_url = Column(String, nullable=True)
    created_at = Column(DateTime)
    uploaded_at = Column(DateTime)
    width = Column(Integer)
    height = Column(Integer)
    coord = Column(JSONB, nullable=True)
    camera_model = Column(String, nullable=True)
    preprocessed = Column(Boolean, default=False, nullable=False)
    mappable = Column(Boolean, default=False)
    panoramic = Column(Boolean, default=False)
    thermal = Column(Boolean, default=False)
    
    # relationships
    mapping_report = relationship("MappingReport", back_populates="images")
    mapping_data = relationship("MappingData", back_populates="image", uselist=False, cascade="all, delete")
    # pano_data = relationship("PanoData", back_populates="image", uselist=False)
    thermal_data = relationship("ThermalData", back_populates="image", uselist=False, cascade="all, delete", foreign_keys="[ThermalData.image_id]")
    counterpart_thermal_data = relationship("ThermalData", back_populates="counterpart", foreign_keys="[ThermalData.counterpart_id]")
    map_elements = relationship("MapElement", back_populates="image")
    detections = relationship("Detection", back_populates="image", cascade="all, delete")

class MappingData(Base):
    __tablename__ = "mapping_data"

    id = Column(Integer, primary_key=True, index=True)
    image_id = Column(Integer, ForeignKey("images.id"), index=True)
    fov = Column(Float)
    rel_altitude = Column(Float, default=100.0)
    rel_altitude_method = Column(String, default="exif") # alternative would be 'googleapi' or 'manual'
    altitude = Column(Float, nullable=True)  # altitude in meters (only needed for googleapi method)
    cam_pitch = Column(Float, nullable=True)
    cam_roll = Column(Float, nullable=True)
    cam_yaw = Column(Float, nullable=True)
    uav_pitch = Column(Float)
    uav_roll = Column(Float)
    uav_yaw = Column(Float)

    # relationships
    image = relationship("Image", back_populates="mapping_data")

class ThermalData(Base):
    __tablename__ = "thermal_data"

    id = Column(Integer, primary_key=True, index=True)
    image_id = Column(Integer, ForeignKey("images.id"), index=True)
    counterpart_id = Column(Integer, ForeignKey("images.id"), nullable=True)  # For fitting rgb image from the same moment
    counterpart_scale = Column(Float, default=1.1)
    min_temp = Column(Float)
    max_temp = Column(Float)
    temp_matrix_path = Column(String, nullable=True)  # Path to the .npy file containing the thermal matrix
    temp_embedded = Column(Boolean, default=True)
    temp_unit = Column(String, default="C")
    lut_name = Column(String, nullable=True)

    # relationships
    image = relationship("Image", foreign_keys=[image_id], back_populates="thermal_data")
    counterpart = relationship("Image", foreign_keys=[counterpart_id], back_populates="counterpart_thermal_data")


class Detection(Base):
    __tablename__ = "detections"

    id = Column(Integer, primary_key=True, index=True)
    image_id = Column(Integer, ForeignKey("images.id"), index=True)
    class_name = Column(String)
    score = Column(Float)
    bbox = Column(JSONB)
    manually_verified = Column(Boolean, default=False)
    coord = Column(JSONB, nullable=True)

    # relationships
    image = relationship("Image", back_populates="detections")