from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict


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
    mapping_report_id: Optional[int] = None
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
    model_config = ConfigDict(from_attributes=True)

class ImageBasicPlusOut(ImageBase):
    id: int
    mapping_data: Optional["MappingDataOut"] = None
    thermal_data: Optional["ThermalDataOut"] = None
    model_config = ConfigDict(from_attributes=True)

class ImageUploadResult(BaseModel):
    status: str  # "success" | "error" | "duplicate"
    filename: Optional[str] = None
    error: Optional[str] = None
    image_object: Optional[ImageOut] = None


class VideoUploadResult(BaseModel):
    status: str           # "uploaded" | "skipped" | "error"
    filename: Optional[str] = None
    message: Optional[str] = None


class UploadSummary(BaseModel):
    report_type: str                        # "mapping" | "reconstruction_360" | "unchanged"
    images: List[ImageUploadResult] = []
    video: Optional[VideoUploadResult] = None
    warnings: List[str] = []


##################
## Mapping Data
##################

class MappingDataBase(BaseModel):
    image_id: int
    fov: Optional[float] = None
    fov_method: Optional[str] = None
    rel_altitude: Optional[float] = None
    altitude: Optional[float] = None
    rel_altitude_method: Optional[str] = "exif"
    cam_pitch: Optional[float] = None
    cam_pitch_method: Optional[str] = None
    cam_roll: Optional[float] = None
    cam_roll_method: Optional[str] = None
    cam_yaw: Optional[float] = None
    cam_yaw_method: Optional[str] = None
    uav_pitch: float
    uav_roll: float
    uav_yaw: float

class MappingDataCreate(MappingDataBase):
    pass

class MappingDataUpdate(BaseModel):
    image_id: Optional[int] = None
    fov: Optional[float] = None
    fov_method: Optional[str] = None
    rel_altitude: Optional[float] = None
    altitude: Optional[float] = None
    rel_altitude_method: Optional[str] = None
    cam_pitch: Optional[float] = None
    cam_pitch_method: Optional[str] = None
    cam_roll: Optional[float] = None
    cam_roll_method: Optional[str] = None
    cam_yaw: Optional[float] = None
    cam_yaw_method: Optional[str] = None
    uav_pitch: Optional[float] = None
    uav_roll: Optional[float] = None
    uav_yaw: Optional[float] = None

class MappingDataOut(MappingDataBase):
    id: int
    model_config = ConfigDict(from_attributes=True)



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
    model_config = ConfigDict(from_attributes=True)


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
    coord: Optional[dict] = None  # JSONB as dict
    unique_object_id: Optional[int] = None  # per-report object cluster label (reID)


class DetectionCreate(DetectionBase):
    pass

class DetectionUpdate(BaseModel):
    id: int
    image_id: Optional[int] = None
    class_name: Optional[str] = None
    score: Optional[float] = None
    bbox: Optional[list] = None  # JSONB as dict
    manually_verified: Optional[bool] = None
    coord: Optional[dict] = None  # JSONB as dict
    unique_object_id: Optional[int] = None  # explicit null clears the assignment

class DetectionOut(DetectionBase):
    id: int
    model_config = ConfigDict(from_attributes=True)



class DetectionSettings(BaseModel):
    processing_mode: str

class DetectionIncremental(BaseModel):
    known_ids: List[int]


class DetectionUniqueObjectAssign(BaseModel):
    unique_object_id: Optional[int] = None  # None clears the assignment
    detection_ids: List[int]


class DetectionObjectGroup(BaseModel):
    unique_object_id: Optional[int] = None  # None = ungrouped bucket
    detections: List[DetectionOut] = []


##################
## ReID (object re-identification)
##################

class ReidDetection(BaseModel):
    id: int
    image_id: int
    bbox: list  # [x, y, w, h] in absolute pixels
    class_name: Optional[str] = None


class ReidImage(BaseModel):
    id: int
    path: str                              # image path (relative reports_data/...)
    width: Optional[int] = None
    height: Optional[int] = None
    # 4 GPS corners [TL, TR, BR, BL], each [lat, lon]; None if not georeferenced
    corners_gps: Optional[List[List[float]]] = None
    # [x0, y0, x1, y1] — the image region corners_gps was traced from (the whole
    # frame normally, the lower half for steeply tilted footprints). None on
    # reports mapped before this was recorded; consumers assume the full frame.
    corners_src_px: Optional[List[int]] = None


class ReidInput(BaseModel):
    detections: List[ReidDetection] = []
    images: List[ReidImage] = []


class DetectionUniqueObjectsBulk(BaseModel):
    # {unique_object_id (as string key): [detection_id, ...]}
    clusters: dict[str, List[int]]


##################
## Fire map (vector overlay from fire-class detections)
##################

class FireMapRegionImage(BaseModel):
    image_id: int
    filename: Optional[str] = None
    thumbnail_url: Optional[str] = None


class FireMapRegion(BaseModel):
    max_score: float
    detection_count: int
    images: List[FireMapRegionImage] = []


class FireMapOut(BaseModel):
    # GeoJSON FeatureCollection (band polygons, [lon, lat] coordinates) or
    # None when the report has no georeferenced fire detections.
    geojson: Optional[dict] = None
    # region_id (string key) -> source images/detections of that fire region
    regions: dict[str, FireMapRegion] = {}