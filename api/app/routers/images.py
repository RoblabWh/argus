from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from typing import List


from app.database import get_db

# Import schemas
from app.schemas.image import ImageOut, ImageCreate, ImageUpdate, ImageUploadResult

# Import CRUD logic
import app.crud.images as crud_image

from app.services.image_processing import process_image

router = APIRouter(prefix="/images", tags=["Images"])


@router.get("/", response_model=List[ImageOut])
def list_images(db: Session = Depends(get_db)):
    return crud_image.get_all(db)


# @router.post("/{report_id}", response_model=ImageOut)
# def create_image(report_id: int, image: ImageCreate, db: Session = Depends(get_db)):
#     return crud_image.create(db, image)

@router.post("/report/{report_id}", response_model=List[ImageUploadResult])
def create_images_batch(report_id: int, files: List[UploadFile] = File(...), db: Session = Depends(get_db)):
    if not files:
        raise HTTPException(status_code=400, detail="No images provided")

    responses = [process_image(report_id, file, db) for file in files]
    return responses

@router.get("/report/{report_id}", response_model=List[ImageOut])
def get_images_by_report(report_id: int, db: Session = Depends(get_db)):
    images = crud_image.get_by_report(db, report_id)
    if not images:
        raise HTTPException(status_code=404, detail="No images found for this report")
    return images

@router.get("/{image_id}", response_model=ImageOut)
def get_image(image_id: int, db: Session = Depends(get_db)):
    return crud_image.get_full_image(db, image_id)


@router.put("/{image_id}", response_model=ImageOut)
def update_image(image_id: int, update: ImageUpdate, db: Session = Depends(get_db)):
    return crud_image.update(db, image_id, update)


@router.delete("/{image_id}")
def delete_image(image_id: int, db: Session = Depends(get_db)):
    return crud_image.delete(db, image_id)


