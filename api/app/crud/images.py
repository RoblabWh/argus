from sqlalchemy.orm import Session, joinedload
from datetime import datetime

from app import models
from app.schemas.image import ImageCreate, ImageUpdate, ImageUploadResult, MappingDataCreate, ThermalDataCreate
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
        .filter(models.Image.id == image_id)
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


def create_mapping_data(db: Session, data: MappingDataCreate):
    mapping_data_in = MappingDataCreate(**data)
    new_mapping_data = models.MappingData(
        **mapping_data_in.dict(),
    )
    db.add(new_mapping_data)
    db.commit()
    db.refresh(new_mapping_data)
    return get_full_image(db, new_mapping_data.image_id) 

def create_multiple_thermal_data(db: Session, data: list[ThermalDataCreate]):
    image_ids = [td.image_id for td in data]
    db.query(models.ThermalData).filter(models.ThermalData.image_id.in_(image_ids)).delete(synchronize_session=False)
    db.commit()

    new_thermal_data_list = [models.ThermalData(**thermal_data.dict()) for thermal_data in data]
    db.add_all(new_thermal_data_list)
    db.commit()
    return new_thermal_data_list

def get_all_thermal_data(db: Session):
    return db.query(models.ThermalData).all()

def delete_thermal_data(db: Session, thermal_data_id: int):
    thermal_data = db.query(models.ThermalData).filter(models.ThermalData.id == thermal_data_id).first()
    if not thermal_data:
        raise ValueError("Thermal data not found")
    
    db.delete(thermal_data)
    db.commit()
    return {"status": "success", "message": "Thermal data deleted successfully"}

def delete_all_thermal_data(db: Session):
    db.query(models.ThermalData).delete()
    db.commit()
    return {"status": "success", "message": "All thermal data deleted successfully"}

def update_thermal_matrix_path(db: Session, image_id: int, new_path: str):
    thermal_data = db.query(models.ThermalData).filter(models.ThermalData.image_id == image_id).first()
    if not thermal_data:
        raise ValueError("Thermal data not found for this image")

    thermal_data.temp_matrix_path = new_path
    db.commit()
    db.refresh(thermal_data)
    return thermal_data