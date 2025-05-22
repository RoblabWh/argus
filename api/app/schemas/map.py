from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


##################
## Map
##################

class MapBase(BaseModel):
    report_id: int
    name: str
    url: str
    status: Optional[str] = "unprocessed"

class MapCreate(MapBase):
    pass

class MapUpdate(BaseModel):
    name: Optional[str] = None
    url: Optional[str] = None
    status: Optional[str] = None

class MapOut(MapBase):
    id: int
    created_at: datetime
    map_elements: List["MapElementOut"] = []

    class Config:
        orm_mode = True



##################
## Map Element
##################

class MapElementBase(BaseModel):
    map_id: int
    image_id: int
    index: int
    coord: dict  # JSONB as dict
    corners: dict  # JSONB as dict
    px_coord: dict  # JSONB as dict
    px_corners: dict  # JSONB as dict

class MapElementCreate(MapElementBase):
    pass

class MapElementUpdate(BaseModel):
    map_id: Optional[int] = None
    image_id: Optional[int] = None
    index: Optional[int] = None
    coord: Optional[dict] = None  # JSONB as dict
    corners: Optional[dict] = None  # JSONB as dict
    px_coord: Optional[dict] = None  # JSONB as dict
    px_corners: Optional[dict] = None  # JSONB as dict

class MapElementOut(MapElementBase):
    id: int
    map: Optional[MapOut] = None
    # image: Optional["ImageOut"] = None

    class Config:
        orm_mode = True