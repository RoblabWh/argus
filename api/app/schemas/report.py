from datetime import datetime
from typing import List, Optional
from .image import ImageOut
from .map import MapOut, MapOutSlim
from .weather import WeatherOut

from pydantic import BaseModel, ConfigDict


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
    model_config = ConfigDict(from_attributes=True)

class ReportDetailOut(ReportOut):
    mapping_report: Optional["MappingReportOut"] = None
    pano_report: Optional["PanoReportOut"] = None
    reconstruction_report: Optional["ReconstructionReportOut"] = None

class ReportSmallDetailOut(ReportOut):
    mapping_report: Optional["MappingReportSimpleOut"] = None
    pano_report: Optional["PanoReportOut"] = None
    reconstruction_report: Optional["ReconstructionReportOut"] = None

class ReportSmallDetailPlusOut(ReportOut):
    mapping_report: Optional["MappingReportSimplePlusOut"] = None
    pano_report: Optional["PanoReportOut"] = None
    reconstruction_report: Optional["ReconstructionReportOut"] = None

class ProcessingSettings(BaseModel):
    keep_weather: Optional[bool] = False
    fast_mapping: bool = True
    target_map_resolution: Optional[int] = None
    accepted_gimbal_tilt_deviation: Optional[float] = None
    apply_manual_defaults: bool = True              # if False, images with manual method fields are marked non-mappable
    default_flight_height: Optional[float] = None
    default_fov: Optional[float] = None
    default_cam_pitch: Optional[float] = None
    cam_orientation_source: Optional[str] = "uav"   # "uav" | "manual"
    default_cam_yaw: Optional[float] = None          # used when source="manual"
    default_cam_roll: Optional[float] = None         # used when source="manual"
    odm_processing: bool = False
    odm_full: bool = False
    reread_metadata: Optional[bool] = False



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
    processing_settings: Optional[dict] = None


class MappingReportCreate(MappingReportBase):
    pass


class MappingReportUpdate(BaseModel):
    flight_timestamp: Optional[datetime] = None
    coord: Optional[dict] = None
    address: Optional[str] = None
    flight_duration: Optional[float] = None
    flight_height: Optional[float] = None
    default_flight_height: Optional[float] = None
    covered_area: Optional[float] = None
    uav: Optional[str] = None
    image_count: Optional[int] = None
    webodm_project_id: Optional[str] = None


class MappingReportOut(MappingReportBase):
    id: int
    images: List[ImageOut] = []
    maps: List[MapOut] = []
    weather: List[WeatherOut] = []
    model_config = ConfigDict(from_attributes=True)

class MappingReportSimpleOut(MappingReportBase):
    id: int
    model_config = ConfigDict(from_attributes=True)

class MappingReportSimplePlusOut(MappingReportBase):
    id: int
    weather: List[WeatherOut] = []
    model_config = ConfigDict(from_attributes=True)




##################
## Reconstruction Report (360° video)
##################

class ReconstructionSettings(BaseModel):
    preset: str = "sparse"          # "sparse" | "dense_fast" | "dense_detail"
    frame_step: int = 1             # process every Nth frame
    config_overrides: dict = {}

class ReconstructionReportOut(BaseModel):
    id: int
    report_id: int
    video_path: Optional[str] = None
    video_duration: Optional[float] = None
    keyframe_count: int = 0
    processing_settings: Optional[dict] = None
    has_dense_pointcloud: bool = False
    flight_timestamp: Optional[datetime] = None
    camera_model: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)


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
    model_config = ConfigDict(from_attributes=True)



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
    detection_count: int
    coord: Optional[dict] = None
    maps: List[MapOutSlim] = []
