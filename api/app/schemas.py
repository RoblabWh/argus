from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class ReportCreate(BaseModel):
    type: str
    title: str
    description: str
    status: Optional[str] = "unprocessed"
    updated_at: Optional[datetime] = None  
    processing_duration: Optional[float] = None
    requires_reprocessing: Optional[bool] = False
    auto_description: Optional[str] = None

class Report(ReportCreate):
    report_id: int
    created_at: datetime

    class Config:
        orm_mode = True

class ReportUpdate(BaseModel):
    type: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    updated_at: Optional[datetime] = None
    processing_duration: Optional[float] = None
    requires_reprocessing: Optional[bool] = None
    auto_description: Optional[str] = None
