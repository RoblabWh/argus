from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


##################
## Image
##################

class ImageBase(BaseModel):
    report_id: int
    url: str
    thumbnail_url: str
    created_at: Optional[datetime] = None
    uploaded_at: Optional[datetime] = None
    width: int
    height: int
    coord: Optional[dict] = None  # JSONB as dict
    camera_model: Optional[str] = None
    mappable: Optional[bool] = False
    panoramic: Optional[bool] = False
    thermal: Optional[bool] = False
    

class ImageCreate(ImageBase):
    pass

class ImageUpdate(BaseModel):
    report_id: Optional[int] = None
    url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    created_at: Optional[datetime] = None
    uploaded_at: Optional[datetime] = None
    width: Optional[int] = None
    height: Optional[int] = None
    coord: Optional[dict] = None  # JSONB as dict
    camera_model: Optional[str] = None
    mappable: Optional[bool] = None
    panoramic: Optional[bool] = None
    thermal: Optional[bool] = None

class ImageOut(ImageBase):
    id: int
    mapping_data: Optional["MappingDataOut"] = None
    thermal_data: Optional["ThermalDataOut"] = None
    detections: List["DetectionOut"] = []

    class Config:
        orm_mode = True    



##################
## Mapping Data
##################

class MappingDataBase(BaseModel):
    image_id: int
    fov: float
    rel_altitude: Optional[float] = 100.0
    cam_pitch: float
    cam_roll: float
    cam_yaw: float
    uav_pitch: Optional[float] = None
    uav_roll: Optional[float] = None
    uav_yaw: Optional[float] = None

class MappingDataCreate(MappingDataBase):
    pass

class MappingDataUpdate(BaseModel):
    image_id: Optional[int] = None
    fov: Optional[float] = None
    rel_altitude: Optional[float] = None
    cam_pitch: Optional[float] = None
    cam_roll: Optional[float] = None
    cam_yaw: Optional[float] = None
    uav_pitch: Optional[float] = None
    uav_roll: Optional[float] = None
    uav_yaw: Optional[float] = None

class MappingDataOut(MappingDataBase):
    id: int
    image: Optional[ImageOut] = None

    class Config:
        orm_mode = True



##################
## Thermal Data
##################

class ThermalDataBase(BaseModel):
    image_id: int
    min_temp: float
    max_temp: float
    temp_matrix: List[List[float]]  # Stored as JSONB in the database
    temp_embedded: Optional[bool] = True
    temp_unit: Optional[str] = "C"
    lut_name: Optional[str] = None

class ThermalDataCreate(ThermalDataBase):
    pass

class ThermalDataUpdate(BaseModel):
    image_id: Optional[int] = None
    min_temp: Optional[float] = None
    max_temp: Optional[float] = None
    temp_matrix: Optional[List[List[float]]] = None  # Stored as JSONB in the database
    temp_embedded: Optional[bool] = None
    temp_unit: Optional[str] = None
    lut_name: Optional[str] = None

class ThermalDataOut(ThermalDataBase):
    id: int
    image: Optional[ImageOut] = None

    class Config:
        orm_mode = True

##################
## Detection
##################

class DetectionBase(BaseModel):
    image_id: int
    class_name: str
    score: float
    bbox: dict  # JSONB as dict

class DetectionCreate(DetectionBase):
    pass

class DetectionUpdate(BaseModel):
    image_id: Optional[int] = None
    class_name: Optional[str] = None
    score: Optional[float] = None
    bbox: Optional[dict] = None  # JSONB as dict

class DetectionOut(DetectionBase):
    id: int
    image: Optional[ImageOut] = None

    class Config:
        orm_mode = True