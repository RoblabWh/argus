from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


##################
## Image
##################

class ImageBase(BaseModel):
    mapping_report_id: int
    filename: str
    url: str
    thumbnail_url: str
    preprocessed: Optional[bool] = False  
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
        from_attributes=True


class ImageUploadResult(BaseModel):
    status: str  # "success" | "error" | "duplicate"
    filename: Optional[str] = None
    error: Optional[str] = None
    image_object: Optional[ImageOut] = None



##################
## Mapping Data
##################

class MappingDataBase(BaseModel):
    image_id: int
    fov: float
    rel_altitude: Optional[float] = 100.0
    altitude: Optional[float] = None  
    rel_altitude_method: Optional[str] = "exif"  
    cam_pitch: Optional[float] = None
    cam_roll: Optional[float] = None
    cam_yaw: Optional[float] = None
    uav_pitch: float
    uav_roll: float
    uav_yaw: float

class MappingDataCreate(MappingDataBase):
    pass

class MappingDataUpdate(BaseModel):
    image_id: Optional[int] = None
    fov: Optional[float] = None
    rel_altitude: Optional[float] = None
    altitude: Optional[float] = None
    rel_altitude_method: Optional[str] = None
    cam_pitch: Optional[float] = None
    cam_roll: Optional[float] = None
    cam_yaw: Optional[float] = None
    uav_pitch: Optional[float] = None
    uav_roll: Optional[float] = None
    uav_yaw: Optional[float] = None

class MappingDataOut(MappingDataBase):
    id: int

    class Config:
        orm_mode = True
        from_attributes=True



##################
## Thermal Data
##################

class ThermalDataBase(BaseModel):
    image_id: int
    counterpart_id: Optional[int] = None  # For fitting rgb image from the same moment
    counterpart_scale: Optional[float] = 1.1
    min_temp: Optional[float] = None
    max_temp: Optional[float] = None
    temp_matrix_path: Optional[str] = None  # Path to the .npy file containing the thermal matrix
    temp_embedded: Optional[bool] = True
    temp_unit: Optional[str] = "C"
    lut_name: Optional[str] = None

class ThermalDataCreate(ThermalDataBase):
    pass

class ThermalDataUpdate(BaseModel):
    image_id: Optional[int] = None
    counterpart_id: Optional[int] = None  # For fitting rgb image from the same moment
    counterpart_scale: Optional[float] = None
    min_temp: Optional[float] = None
    max_temp: Optional[float] = None
    temp_matrix_path: Optional[str] = None  # Path to the .npy file containing the thermal matrix
    temp_embedded: Optional[bool] = True
    temp_unit: Optional[str] = None
    lut_name: Optional[str] = None

class ThermalDataOut(ThermalDataBase):
    id: int
    #image: Optional[ImageOut] = None

    class Config:
        orm_mode = True
        from_attributes=True


class ThermalMatrixResponse(BaseModel):
    image_id: int
    min_temp: float
    max_temp: float
    matrix: List[List[float]]  # or int if they're integers

##################
## Detection
##################

class DetectionBase(BaseModel):
    image_id: int
    class_name: str
    score: float
    bbox: list  # JSONB as dict
    manually_verified: Optional[bool] = None


class DetectionCreate(DetectionBase):
    pass

class DetectionUpdate(BaseModel):
    image_id: Optional[int] = None
    class_name: Optional[str] = None
    score: Optional[float] = None
    bbox: Optional[list] = None  # JSONB as dict
    manually_verified: Optional[bool] = None

class DetectionOut(DetectionBase):
    id: int
    #image: Optional[ImageOut] = None

    class Config:
        orm_mode = True



