from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from typing import List
from sqlalchemy.orm import Session
from app.database import get_db
import requests


# Import schemas
from app.schemas.image import ImageOut, ImageCreate, ImageUpdate, ImageUploadResult, ThermalMatrixResponse

# Import CRUD logic
import app.crud.report as crud_report

from app.services.odm import WebodmManager

router = APIRouter(prefix="/odm", tags=["OpenDroneMap"])

odm_manager = WebodmManager()

@router.get("/", response_model=dict)
def is_odm_available(db: Session = Depends(get_db)):
    #check if WebODM is enabled and if it is reachable
    return {"is_available": odm_manager.check_connection(), "url": odm_manager.url}


@router.get("/projects", response_model=List[dict])
def get_all_projects(db: Session = Depends(get_db)):    
    projects = odm_manager.get_all_projects()
    if projects is None:
        raise HTTPException(status_code=500, detail="Failed to fetch projects from WebODM")
    
    return projects

@router.get("/projects/{project_id}", response_model=bool)
def check_project_exists(project_id: str, db: Session = Depends(get_db)):
    if not odm_manager.check_connection():
        raise HTTPException(status_code=503, detail="WebODM is not available")

    exists = odm_manager.check_project_exists(project_id)
    if not exists:
        raise HTTPException(status_code=404, detail="Project not found")

    return exists

@router.get("/projects/{project_id}/tasks", response_model=List[dict])
def get_project_tasks(project_id: str, db: Session = Depends(get_db)):
    if not odm_manager.check_connection():
        raise HTTPException(status_code=503, detail="WebODM is not available")

    tasks = odm_manager.get_project_tasks(project_id)
    if tasks is None:
        raise HTTPException(status_code=404, detail="Tasks not found")

    return tasks

