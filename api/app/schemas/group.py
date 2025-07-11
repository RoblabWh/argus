from datetime import datetime
from typing import List, Optional
from .report import ReportOut, ReportDetailOut, ReportSmallDetailOut

from pydantic import BaseModel


##################
## Group
##################

class GroupBase(BaseModel):
    name: str
    description: Optional[str] = None

class GroupCreate(GroupBase):
    pass


class GroupUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class GroupOut(GroupBase):
    id: int
    created_at: datetime
    reports: List[ReportOut] = []

    class Config:
        orm_mode = True

class GroupOutReportMetadata(GroupBase):
    id: int
    created_at: datetime
    reports: List[ReportSmallDetailOut] = []

    class Config:
        orm_mode = True