from sqlalchemy import Column, Integer, String, DateTime, Boolean, Float, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base

# Define the
# - Report,
# - MappingReport and
# - PanoReport
# classes to represent the reports and their details in the database.


class Report(Base):
    __tablename__ = "reports"

    report_id = Column(Integer, primary_key=True, index=True)
    group_id = Column(Integer, ForeignKey("groups.id"), index=True, nullable=True)
    type = Column(String, index=True, default="unset")
    title = Column(String)
    description = Column(String)
    status = Column(String, default="unprocessed")
    created_at = Column(DateTime, index=True, server_default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    processing_duration = Column(Float, nullable=True)
    requires_reprocessing = Column(Boolean, default=False)
    auto_description = Column(String, nullable=True)

    # relationships
    group = relationship("Group", back_populates="reports")
    mapping_report = relationship("MappingReport", back_populates="report", uselist=False, cascade="all, delete")
    pano_report = relationship("PanoReport", back_populates="report", uselist=False, cascade="all, delete")



class MappingReport(Base):
    __tablename__ = "mapping_reports"

    id = Column(Integer, primary_key=True, index=True)
    report_id = Column(Integer, ForeignKey("reports.report_id"), index=True)
    flight_timestamp = Column(DateTime, index=True, nullable=True)
    coord = Column(JSONB, nullable=True)
    address = Column(String, nullable=True)
    flight_duration = Column(Float, nullable=True)
    flight_height = Column(Float, nullable=True)
    covered_area = Column(Float, nullable=True)
    uav = Column(String, default="Unknown")
    image_count = Column(Integer, default=0)

    #relationships
    report = relationship("Report", back_populates="mapping_report")
    images = relationship("Image", back_populates="mapping_report", cascade="all, delete")
    weather = relationship("Weather", back_populates="mapping_report", cascade="all, delete")
    maps = relationship("Map", back_populates="mapping_report", cascade="all, delete")




class PanoReport(Base):
    __tablename__ = "pano_reports"

    id = Column(Integer, primary_key=True, index=True)
    report_id = Column(Integer, ForeignKey("reports.report_id"), index=True)
    video_duration = Column(Float, nullable=True)

    # relationships
    report = relationship("Report", back_populates="pano_report")
