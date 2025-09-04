from datetime import datetime
from typing import List, Optional
from .image import ImageOut
from .map import MapOut, MapOutSlim
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

class ReportSmallDetailOut(ReportOut):
    mapping_report: Optional["MappingReportSimpleOut"] = None
    pano_report: Optional["PanoReportOut"] = None

class ReportSmallDetailPlusOut(ReportOut):
    mapping_report: Optional["MappingReportSimplePlusOut"] = None
    pano_report: Optional["PanoReportOut"] = None

class ProcessingSettings(BaseModel):
    keep_weather: Optional[bool] = False
    fast_mapping: bool = True
    target_map_resolution: Optional[int] = None
    accepted_gimbal_tilt_deviation: Optional[float] = None
    default_flight_height: Optional[float] = None
    odm_processing: bool = False
    odm_full: bool = False


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
    default_flight_height: Optional[float] = None
    covered_area: Optional[float] = None
    uav: Optional[str] = "Unknown"
    image_count: Optional[int] = 0
    webodm_project_id: Optional[str] = None


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

class MappingReportSimpleOut(MappingReportBase):
    id: int

    class Config:
        orm_mode = True


class MappingReportSimplePlusOut(MappingReportBase):
    id: int
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



##################
## aggregated Report Data
##################

class ReportSummary(BaseModel):
    report_id: int
    title: str
    description: Optional[str]
    type: str
    status: str
    created_at: datetime
    flight_timestamp: Optional[datetime]
    image_count: int
    pano_count: int
    thermal_count: int
    coord: Optional[dict] = None
    maps: List[MapOutSlim] = []
