from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List


from app.database import get_db

# Import schemas
from app.schemas.group import GroupCreate, GroupUpdate, GroupOut, GroupOutReportMetadata
from app.schemas.report import ReportDetailOut  

# Import CRUD logic
import app.crud.groups as crud_group

router = APIRouter(prefix="/groups", tags=["Groups"])


@router.get("/", response_model=List[GroupOutReportMetadata])
def list_groups(db: Session = Depends(get_db)):
    print("Fetching all groups with report metadata")
    return crud_group.get_all_with_report_metadata(db)
    #return crud_group.get_all(db)


@router.post("/", response_model=GroupOut)
def create_group(group: GroupCreate, db: Session = Depends(get_db)):
    return crud_group.create(db, group)


@router.get("/{group_id}", response_model=GroupOut)
def get_group(group_id: int, db: Session = Depends(get_db)):
    return crud_group.get(db, group_id)


@router.put("/{group_id}", response_model=GroupOut)
def update_group(group_id: int, update: GroupUpdate, db: Session = Depends(get_db)):
    return crud_group.update(db, group_id, update)


@router.delete("/{group_id}")
def delete_group(group_id: int, db: Session = Depends(get_db)):
    return crud_group.delete(db, group_id)


@router.get("/{group_id}/reports", response_model=List[ReportDetailOut])
def get_group_reports(group_id: int, db: Session = Depends(get_db)):
    return crud_group.get_reports_by_group_full(db, group_id)
