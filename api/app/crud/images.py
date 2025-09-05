from sqlalchemy.orm import Session, joinedload
from datetime import datetime

from app import models
from app.schemas.image import ImageCreate, ImageUpdate, ImageUploadResult, MappingDataCreate, ThermalDataCreate, DetectionUpdate
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
    mapping_report = db.query(models.MappingReport).filter(models.MappingReport.report_id == report_id).first()
    if not mapping_report:
        return []
    return (
        db.query(models.Image)
        .filter(models.Image.mapping_report_id == mapping_report.id)
        .options(
            joinedload(models.Image.mapping_data),
            joinedload(models.Image.thermal_data),
            #joinedload(models.Image.detections),
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




######################
############## Thermal
######################


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



######################
########### Detections
######################

def get_images_for_detection(db: Session, mapping_report_id: int):
    images = db.query(models.Image).filter(models.Image.mapping_report_id == mapping_report_id).all()
    return [{"path": image.url, "id": image.id} for image in images if not image.thermal]

def get_detections_by_mapping_report_id(db: Session, mapping_report_id: int):
    # 1. load images from the mapping report with their detections
    # then only return the detections
    images = (
        db.query(models.Image)
        .filter(models.Image.mapping_report_id == mapping_report_id)
        .options(joinedload(models.Image.detections))
        .all()
    )
    detections = []
    for image in images:
        detections.extend(image.detections)
    return detections


def save_detections(db: Session, mapping_report_id: int, detections: dict):
    images = db.query(models.Image).filter(models.Image.mapping_report_id == mapping_report_id).all()
    image_id_map = {image.id: image for image in images}

    for det in detections.get("detections", []):
        image_id = det.get("image_id")
        if image_id in image_id_map:
            new_detection = models.Detection(
                image_id=image_id,
                class_name=det.get("category_name"),
                bbox=det.get("bbox"),
                score=det.get("score"),
                manually_verified=False
            )
            db.add(new_detection)

    db.commit()
    return {"status": "success", "message": "Detections saved successfully"}

def get_all_detections(db: Session):
    return db.query(models.Detection).all()

def delete_all_detections_by_mapping_report_id(db: Session, mapping_report_id: int):
    db.query(models.Detection).filter(models.Detection.image.has(mapping_report_id=mapping_report_id)).delete(synchronize_session=False)
    db.commit()
    return {"status": "success", "message": "All detections deleted successfully"}

def update_detection(db: Session, detection_id: int, update_data: DetectionUpdate):
    detection = db.query(models.Detection).filter(models.Detection.id == detection_id).first()
    if not detection:
        raise ValueError("Detection not found")

    for key, value in update_data.dict(exclude_unset=True).items():
        setattr(detection, key, value)

    db.commit()
    db.refresh(detection)
    return detection

def delete_detection(db: Session, detection_id: int):
    detection = db.query(models.Detection).filter(models.Detection.id == detection_id).first()
    if not detection:
        raise ValueError("Detection not found")
    
    db.delete(detection)
    db.commit()
    return {"status": "success", "message": "Detection deleted successfully"}

def update_detections_coords_by_mapping_report_id(db: Session, mapping_report_id: int):
    images = db.query(models.Image).filter(models.Image.mapping_report_id == mapping_report_id).all()
    for image in images:
        for detection in image.detections:
            detection.coord = image.coord
    db.commit()
    return {"status": "success", "message": "Detection coordinates updated successfully"}