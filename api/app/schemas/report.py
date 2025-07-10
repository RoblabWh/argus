from datetime import datetime
from typing import List, Optional
from .image import ImageOut
from .map import MapOut
from .weather import WeatherOut

from pydantic import BaseModel


##################
## Report
##################

class ReportBase(BaseModel):
    group_id: int 
    type: Optional[str] = "unset"
    title: str
    description: str
    status: Optional[str] = "unprocessed"
    progress: Optional[float] = 0.0
    processing_duration: Optional[float] = None
    requires_reprocessing: Optional[bool] = False
    auto_description: Optional[str] = None

class ReportCreate(ReportBase):
    pass


class ReportUpdate(BaseModel):
    type: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    updated_at: Optional[datetime] = None
    processing_duration: Optional[float] = None
    requires_reprocessing: Optional[bool] = None
    auto_description: Optional[str] = None

class ReportOut(ReportCreate):
    report_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True

class ReportDetailOut(ReportOut):
    mapping_report: Optional["MappingReportOut"] = None
    pano_report: Optional["PanoReportOut"] = None


class ProcessingSettings(BaseModel):
    preprocessing: bool = True
    processing: bool = True
    keep_weather: bool = False
    odm_orthophoto: bool = False
    odm_full: bool = False
    reprocess_all: bool = False
    default_flight_height: Optional[float] = None


##################
## Mapping Report
##################

class MappingReportBase(BaseModel):
    report_id: int
    flight_timestamp: Optional[datetime] = None
    coord: Optional[dict] = None  # JSONB as dict
    address: Optional[str] = None
    flight_duration: Optional[float] = None
    flight_height: Optional[float] = None
    covered_area: Optional[float] = None
    uav: Optional[str] = "Unknown"
    image_count: Optional[int] = 0


class MappingReportCreate(MappingReportBase):
    pass


class MappingReportUpdate(MappingReportBase):
    pass


class MappingReportOut(MappingReportBase):
    id: int
    images: List[ImageOut] = []
    maps: List[MapOut] = []
    weather: List[WeatherOut] = []

    class Config:
        orm_mode = True




##################
## Pano Report
##################

class PanoReportBase(BaseModel):
    report_id: int
    video_duration: Optional[float] = None

class PanoReportCreate(PanoReportBase):
    pass

class PanoReportUpdate(PanoReportBase):
    pass

class PanoReportOut(PanoReportBase):
    id: int

    class Config:
        orm_mode = True