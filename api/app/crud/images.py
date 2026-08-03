from sqlalchemy.orm import Session, joinedload
from sqlalchemy import select
from sqlalchemy import update as sa_update

from datetime import datetime

from app import models
from app.schemas.image import (
    ImageCreate,
    ImageUpdate,
    ImageUploadResult,
    MappingDataCreate,
    ThermalDataCreate,
    DetectionUpdate,
)
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
    mapping_report = (
        db.query(models.MappingReport)
        .filter(models.MappingReport.report_id == report_id)
        .first()
    )
    if not mapping_report:
        return []
    return (
        db.query(models.Image)
        .filter(models.Image.mapping_report_id == mapping_report.id)
        .options(
            joinedload(models.Image.mapping_data),
            joinedload(models.Image.thermal_data),
        )
        .all()
    )


def get_by_report_full(db: Session, report_id: int):
    mapping_report = (
        db.query(models.MappingReport)
        .filter(models.MappingReport.report_id == report_id)
        .first()
    )
    if not mapping_report:
        return []
    return (
        db.query(models.Image)
        .filter(models.Image.mapping_report_id == mapping_report.id)
        .options(
            joinedload(models.Image.mapping_data),
            joinedload(models.Image.thermal_data),
            joinedload(models.Image.detections),
        )
        .all()
    )


def create(db: Session, data: ImageCreate):
    # img_in = ImageCreate(**data)
    new_image = models.Image(
        **data.model_dump(),
    )
    db.add(new_image)
    db.commit()
    db.refresh(new_image)
    return new_image


def update(db: Session, image_id: int, update_data: ImageUpdate):
    image = db.query(models.Image).filter(models.Image.id == image_id).first()
    if not image:
        raise ValueError("Image not found")

    for key, value in update_data.model_dump(exclude_unset=True).items():
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
    # mapping_data_in = MappingDataCreate(**data)
    new_mapping_data = models.MappingData(
        **data.model_dump(),
    )
    db.add(new_mapping_data)
    db.commit()
    db.refresh(new_mapping_data)
    return get_full_image(db, new_mapping_data.image_id)


def delete_mapping_data(db: Session, image_id: int):
    db.query(models.MappingData).filter(
        models.MappingData.image_id == image_id
    ).delete()
    db.commit()


def mark_images_non_mappable(db: Session, image_ids: list[int]) -> None:
    """Force mappable=False for images whose manual fields are not being applied this run."""
    db.query(models.Image).filter(
        models.Image.id.in_(image_ids)
    ).update({"mappable": False}, synchronize_session=False)
    db.commit()


def persist_mapping_defaults(db: Session, affected_images: list) -> None:
    """Bulk-write fov, rel_altitude, cam_pitch, and mappable for images that had defaults applied.
    Values are read from the already-updated in-memory ORM objects — no separate value passing needed."""

    db.execute(
        sa_update(models.MappingData),
        [
            {
                "id": img.mapping_data.id,
                "fov": img.mapping_data.fov,
                "rel_altitude": img.mapping_data.rel_altitude,
                "cam_pitch": img.mapping_data.cam_pitch,
            }
            for img in affected_images
        ],
    )
    db.execute(
        sa_update(models.Image),
        [{"id": img.id, "mappable": img.mappable} for img in affected_images],
    )
    db.commit()


######################
############## Thermal
######################


def create_multiple_thermal_data(db: Session, data: list[ThermalDataCreate]):
    image_ids = [td.image_id for td in data]
    db.query(models.ThermalData).filter(
        models.ThermalData.image_id.in_(image_ids)
    ).delete(synchronize_session=False)
    db.commit()

    new_thermal_data_list = [
        models.ThermalData(**thermal_data.model_dump()) for thermal_data in data
    ]
    db.add_all(new_thermal_data_list)
    db.commit()
    return new_thermal_data_list


def get_all_thermal_data(db: Session):
    return db.query(models.ThermalData).all()


def delete_thermal_data(db: Session, thermal_data_id: int):
    thermal_data = (
        db.query(models.ThermalData)
        .filter(models.ThermalData.id == thermal_data_id)
        .first()
    )
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
    thermal_data = (
        db.query(models.ThermalData)
        .filter(models.ThermalData.image_id == image_id)
        .first()
    )
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
    images = (
        db.query(models.Image)
        .filter(models.Image.mapping_report_id == mapping_report_id)
        .all()
    )
    # filter out thermal images
    images = [image for image in images if not image.thermal]
    images = [
        {"url": image.url, "id": image.id, "coord": image.coord} for image in images
    ]
    return images


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


def get_incremental_detections(
    db: Session, mapping_report_id: int, known_ids: list[int]
):
    images = (
        db.query(models.Image)
        .filter(models.Image.mapping_report_id == mapping_report_id)
        .options(joinedload(models.Image.detections))
        .all()
    )

    detections = []
    for image in images:
        for detection in image.detections:
            if detection.id not in known_ids:
                detections.append(detection)

    return detections


def save_detections(db: Session, mapping_report_id: int, detections: dict):
    images = (
        db.query(models.Image)
        .filter(models.Image.mapping_report_id == mapping_report_id)
        .all()
    )
    image_id_map = {image.id: image for image in images}

    for det in detections.get("detections", []):
        image_id = det.get("image_id")
        if image_id in image_id_map:
            new_detection = models.Detection(
                image_id=image_id,
                class_name=det.get("category_name"),
                bbox=det.get("bbox"),
                score=det.get("score"),
                manually_verified=False,
                unique_object_id=det.get("unique_object_id"),
            )
            db.add(new_detection)

    db.commit()
    return {"status": "success", "message": "Detections saved successfully"}


def get_all_detections(db: Session):
    return db.query(models.Detection).all()


def delete_all_detections_by_mapping_report_id(db: Session, mapping_report_id: int):
    # db.query(models.Detection).filter(models.Detection.image.has(mapping_report_id=mapping_report_id)).delete(synchronize_session=False)
    # db.query(models.Detection).join(models.Image).filter(
    #     models.Image.mapping_report_id == mapping_report_id
    # ).delete(synchronize_session=False)
    image_ids = select(models.Image.id).where(
        models.Image.mapping_report_id == mapping_report_id
    )
    db.query(models.Detection).filter(
        models.Detection.image_id.in_(image_ids)
    ).delete(synchronize_session=False)
    db.commit()
    return {"status": "success", "message": "All detections deleted successfully"}


def delete_detections_by_class_names(
    db: Session, mapping_report_id: int, class_names, invert: bool = False
):
    """Delete a report's detections scoped by class name.

    ``invert=False`` deletes only detections whose class is in ``class_names``;
    ``invert=True`` deletes everything else (NULL class names included). Lets
    the separately-dispatched fire and object detection runs replace only
    their own results.
    """
    image_ids = select(models.Image.id).where(
        models.Image.mapping_report_id == mapping_report_id
    )
    class_filter = models.Detection.class_name.in_(class_names)
    if invert:
        class_filter = models.Detection.class_name.is_(None) | ~models.Detection.class_name.in_(class_names)
    db.query(models.Detection).filter(
        models.Detection.image_id.in_(image_ids),
        class_filter,
    ).delete(synchronize_session=False)
    db.commit()
    return {"status": "success", "message": "Detections deleted successfully"}


def update_detection(db: Session, detection_id: int, update_data: DetectionUpdate):
    detection = (
        db.query(models.Detection).filter(models.Detection.id == detection_id).first()
    )
    if not detection:
        raise ValueError("Detection not found")

    for key, value in update_data.model_dump(exclude_unset=True).items():
        setattr(detection, key, value)

    db.commit()
    db.refresh(detection)
    return detection


def delete_detection(db: Session, detection_id: int):
    detection = (
        db.query(models.Detection).filter(models.Detection.id == detection_id).first()
    )
    if not detection:
        raise ValueError("Detection not found")

    db.delete(detection)
    db.commit()
    return {"status": "success", "message": "Detection deleted successfully"}


def update_detections_coords_by_mapping_report_id(db: Session, mapping_report_id: int):
    images = (
        db.query(models.Image)
        .filter(models.Image.mapping_report_id == mapping_report_id)
        .all()
    )
    for image in images:
        for detection in image.detections:
            detection.coord = image.coord
    db.commit()
    return {
        "status": "success",
        "message": "Detection coordinates updated successfully",
    }


def update_detections_batch(
    db: Session, mapping_report_id: int, updates: list[DetectionUpdate]
):
    mapping_report = (
        db.query(models.MappingReport)
        .filter(models.MappingReport.id == mapping_report_id)
        .first()
    )
    if not mapping_report:
        raise ValueError("Mapping report not found for this report ID")

    images = (
        db.query(models.Image)
        .filter(models.Image.mapping_report_id == mapping_report.id)
        .all()
    )
    image_id_map = {image.id: image for image in images}

    updated_count = 0
    for update in updates:
        detection = (
            db.query(models.Detection).filter(models.Detection.id == update.id).first()
        )
        if detection and detection.image_id in image_id_map:
            for key, value in update.model_dump(exclude_unset=True).items():
                if key != "id":  # Skip the id field
                    setattr(detection, key, value)
            updated_count += 1

    db.commit()
    return updated_count


def set_unique_object_id_batch(
    db: Session,
    mapping_report_id: int,
    unique_object_id: int | None,
    detection_ids: list[int],
):
    # Restrict the update to detections that belong to this report's images, so a
    # caller cannot (accidentally) re-label detections from another report.
    image_ids = select(models.Image.id).where(
        models.Image.mapping_report_id == mapping_report_id
    )
    updated_count = (
        db.query(models.Detection)
        .filter(
            models.Detection.id.in_(detection_ids),
            models.Detection.image_id.in_(image_ids),
        )
        .update(
            {models.Detection.unique_object_id: unique_object_id},
            synchronize_session=False,
        )
    )
    db.commit()
    return updated_count


def get_reid_input(db: Session, mapping_report_id: int):
    """Assemble the payload the YOLO reID worker needs to cluster detections.

    Returns detections (with DB ids) plus, per non-thermal image, its pixel
    dimensions and 4 GPS corners. Corners come from the report's map elements
    (computed during mapping), stored as [TL, TR, BR, BL] each [lat, lon] —
    exactly the order the worker's bilinear interpolation expects, so they are
    passed through unchanged. Images without a map element get corners_gps=None;
    the worker excludes their detections from re-ID entirely, leaving their
    unique_object_id null (they are neither clustered nor made singletons).
    """
    images = (
        db.query(models.Image)
        .filter(
            models.Image.mapping_report_id == mapping_report_id,
            models.Image.thermal.is_(False),
        )
        .options(joinedload(models.Image.detections))
        .all()
    )

    # image_id -> [TL, TR, BR, BL] of [lat, lon], pulled from map elements.
    corners_by_image: dict[int, list] = {}
    # image_id -> [x0, y0, x1, y1], the image region those corners cover.
    src_px_by_image: dict[int, list] = {}
    map_elements = (
        db.query(models.MapElement)
        .join(models.Map, models.MapElement.map_id == models.Map.id)
        .filter(models.Map.mapping_report_id == mapping_report_id)
        .all()
    )
    for el in map_elements:
        if el.image_id in corners_by_image:
            continue
        gps = (el.corners or {}).get("gps") if el.corners else None
        if gps and len(gps) == 4:
            # Stored order is already [TL, TR, BR, BL] each [lat, lon] — see the
            # production frontend interpolation computeDetectionGps in
            # frontend/src/utils/coordinateUtils.ts. The worker's
            # interpolate_detection_gps expects exactly this order, so pass through.
            corners_by_image[el.image_id] = gps
            src_px = (el.corners or {}).get("src_px")
            if src_px and len(src_px) == 4:
                src_px_by_image[el.image_id] = src_px

    detections: list = []
    images_out: list = []
    for image in images:
        images_out.append(
            {
                "id": image.id,
                "path": image.url,
                "width": image.width,
                "height": image.height,
                "corners_gps": corners_by_image.get(image.id),
                "corners_src_px": src_px_by_image.get(image.id),
            }
        )
        for det in image.detections:
            detections.append(
                {
                    "id": det.id,
                    "image_id": det.image_id,
                    "bbox": det.bbox,
                    "class_name": det.class_name,
                }
            )

    return {"detections": detections, "images": images_out}


def get_fire_map_input(db: Session, mapping_report_id: int, class_names):
    """Assemble the payload the fire-map service needs (services/fire_map.py).

    Like get_reid_input, but only detections whose class is in ``class_names``,
    and images additionally carry filename/thumbnail_url so the map overlay
    can show which source images a fire region originates from. Corner
    convention is unchanged: [TL, TR, BR, BL], each [lat, lon]; images without
    a map element get corners_gps=None and their detections are skipped by
    the service.
    """
    images = (
        db.query(models.Image)
        .filter(
            models.Image.mapping_report_id == mapping_report_id,
            models.Image.thermal.is_(False),
        )
        .options(joinedload(models.Image.detections))
        .all()
    )

    corners_by_image: dict[int, list] = {}
    src_px_by_image: dict[int, list] = {}
    map_elements = (
        db.query(models.MapElement)
        .join(models.Map, models.MapElement.map_id == models.Map.id)
        .filter(models.Map.mapping_report_id == mapping_report_id)
        .all()
    )
    for el in map_elements:
        if el.image_id in corners_by_image:
            continue
        gps = (el.corners or {}).get("gps") if el.corners else None
        if gps and len(gps) == 4:
            corners_by_image[el.image_id] = gps
            src_px = (el.corners or {}).get("src_px")
            if src_px and len(src_px) == 4:
                src_px_by_image[el.image_id] = src_px

    detections: list = []
    images_out: list = []
    for image in images:
        images_out.append(
            {
                "id": image.id,
                "filename": image.filename,
                "thumbnail_url": image.thumbnail_url,
                "width": image.width,
                "height": image.height,
                "corners_gps": corners_by_image.get(image.id),
                "corners_src_px": src_px_by_image.get(image.id),
            }
        )
        for det in image.detections:
            if det.class_name in class_names:
                detections.append(
                    {
                        "id": det.id,
                        "image_id": det.image_id,
                        "bbox": det.bbox,
                        "score": det.score,
                    }
                )

    return {"detections": detections, "images": images_out}


def assign_unique_object_clusters(
    db: Session, mapping_report_id: int, clusters: dict[int, list[int]]
):
    """Bulk-assign reID clusters to a report's detections.

    Clears any previous assignment for the report first, then writes each
    cluster's unique_object_id onto its detections. Returns the count updated.
    """
    image_ids = select(models.Image.id).where(
        models.Image.mapping_report_id == mapping_report_id
    )
    # Reset previous assignments so re-runs are clean.
    db.query(models.Detection).filter(
        models.Detection.image_id.in_(image_ids)
    ).update({models.Detection.unique_object_id: None}, synchronize_session=False)

    updated_count = 0
    for unique_object_id, detection_ids in clusters.items():
        if not detection_ids:
            continue
        updated_count += (
            db.query(models.Detection)
            .filter(
                models.Detection.id.in_(detection_ids),
                models.Detection.image_id.in_(image_ids),
            )
            .update(
                {models.Detection.unique_object_id: unique_object_id},
                synchronize_session=False,
            )
        )
    db.commit()
    return updated_count


def get_detections_grouped_by_object(db: Session, mapping_report_id: int):
    images = (
        db.query(models.Image)
        .filter(models.Image.mapping_report_id == mapping_report_id)
        .options(joinedload(models.Image.detections))
        .all()
    )

    groups: dict[int | None, list] = {}
    for image in images:
        for detection in image.detections:
            groups.setdefault(detection.unique_object_id, []).append(detection)

    return [
        {"unique_object_id": uid, "detections": detections}
        for uid, detections in groups.items()
    ]
