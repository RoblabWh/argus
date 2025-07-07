from sqlalchemy.orm import Session, joinedload
from datetime import datetime

from app import models
from app.schemas.image import ImageCreate, ImageUpdate, ImageUploadResult
from app.services.cleanup import delete_image_file

def get_all(db: Session):
    return db.query(models.Image).all()

def get_full_image(db: Session, image_id: int):
    return (
        db.query(models.Image)
        .options(
            joinedload(models.Image.mapping_data),
            joinedload(models.Image.thermal_data),
            joinedload(models.Image.detections),
        )
        .filter(models.Image.image_id == image_id)
        .first()
    )

def get_by_report(db: Session, report_id: int):
    return (
        db.query(models.Image)
        .filter(models.Image.report_id == report_id)
        .options(
            joinedload(models.Image.mapping_data),
            joinedload(models.Image.thermal_data),
            joinedload(models.Image.detections),
        )
        .all()
    )


def create(db: Session, data: ImageCreate):
    img_in = ImageCreate(**data)
    new_image = models.Image(
        **img_in.dict(),
    )
    db.add(new_image)
    db.commit()
    db.refresh(new_image)
    return new_image

def update(db: Session, image_id: int, update_data: ImageUpdate):
    image = db.query(models.Image).filter(models.Image.image_id == image_id).first()
    if not image:
        raise ValueError("Image not found")

    for key, value in update_data.dict(exclude_unset=True).items():
        setattr(image, key, value)

    db.commit()
    db.refresh(image)
    return image

def delete(db: Session, image_id: int):
    image = db.query(models.Image).filter(models.Image.id == image_id).first()
    if not image:
        raise ValueError("Image not found")
    
    # delete the image file if it exists
    if not delete_image_file(image):
        return {"status": "error", "message": "Failed to delete image file"}
    
    db.delete(image)
    db.commit()
    return {"status": "success", "message": "Image deleted successfully"}