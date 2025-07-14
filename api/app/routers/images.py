from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from typing import List
import time
from concurrent.futures import ThreadPoolExecutor
from fastapi.concurrency import run_in_threadpool


from app.database import get_db

# Import schemas
from app.schemas.image import ImageOut, ImageCreate, ImageUpdate, ImageUploadResult

# Import CRUD logic
import app.crud.images as crud_image

from app.services.image_processing import process_image, check_mapping_report

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
    #track time to evaluate performance
    start_time = time.time()
    #responses = [process_image(report_id, file, db) for file in files]

    mapping_report_id = check_mapping_report(report_id, db)

    def _process(file: UploadFile):
        # Create a new DB session for this thread
        db_local = get_db()
        db_local = next(db_local)  # Get the session from the generator
        try:
            result = process_image(report_id, file, mapping_report_id, db_local)
            db_local.close()
            return result
        except Exception as e:
            db_local.rollback()
            db_local.close()
            return {
                "image_object": None,
                "filename": file.filename,
                "status": "error",
                "error": str(e)
            }

    with ThreadPoolExecutor(max_workers=6) as executor:
        responses = list(executor.map(_process, files))

    end_time = time.time()
    processing_time = end_time - start_time
    print(f"Processed {len(files)} images in {processing_time:.2f} seconds")
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


#Performance Results
# Per Batch: 1.35, 1.06, 1.08, 1.06, 1.07, 1.05, 1.07, 1.08, 1.09, 1.10, 1.08, 1.12, 1.09, 1.11, 1.10, 0.67


