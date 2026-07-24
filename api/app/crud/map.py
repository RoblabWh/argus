from sqlalchemy.orm import Session, joinedload
from datetime import datetime, timezone
from pathlib import Path

from app import models
from app.schemas.map import MapCreate, MapUpdate
from app.schemas.map import MapElementCreate, MapElementUpdate
from app.services.cleanup import delete_file

def get_all(db: Session):
    return db.query(models.Map).all()

def get_full_map(db: Session, map_id: int):
    return (
        db.query(models.Map)
        .options(
            joinedload(models.Map.map_elements)
            .joinedload(models.MapElement.image),
        )
        .filter(models.Map.id == map_id)
        .first()
    )

def get_maps_by_mapping_report(db: Session, mapping_report_id: int):
    return db.query(models.Map).filter(models.Map.mapping_report_id == mapping_report_id).all()

def create(db: Session, data: MapCreate):
    new_map = models.Map(
        **data.model_dump(),
        created_at=datetime.now(timezone.utc),
    )
    db.add(new_map)
    db.commit()
    db.refresh(new_map)
    return new_map

def delete(db: Session, map_id: int):
    map_to_delete = db.query(models.Map).filter(models.Map.id == map_id).first()
    if map_to_delete:
        image_url = map_to_delete.url
        db.delete(map_to_delete)
        db.commit()
        if image_url:
            delete_file(Path(image_url))
        return True
    return False

def create_multiple_map_elements(db: Session, map_id: int, elements: list[MapElementCreate]):
    map_elements = [models.MapElement(**element.dict()) for element in elements]
    db.add_all(map_elements)
    db.commit()
    return map_elements


def get_thermal_map_input(db: Session, mapping_report_id: int):
    """Assemble the payload the thermal-map service needs (services/thermal_map.py).

    Returns the report's IR maps (Map.name pattern ``{method}_ir_{index}``)
    with, per map element, the image's UTM footprint corners plus its raw
    temperature matrix path. Elements whose image has no ThermalData/.npy
    (color-mapped-only thermal images) get temp_matrix_path=None — the
    service skips them.
    """
    ir_maps = (
        db.query(models.Map)
        .options(
            joinedload(models.Map.map_elements)
            .joinedload(models.MapElement.image)
            .joinedload(models.Image.thermal_data)
        )
        .filter(
            models.Map.mapping_report_id == mapping_report_id,
            models.Map.name.contains("_ir_"),
        )
        .all()
    )

    maps_out = []
    for ir_map in ir_maps:
        bounds_utm = (ir_map.bounds or {}).get("utm")
        if not bounds_utm:
            continue
        elements = []
        for el in ir_map.map_elements:
            corners_utm = (el.corners or {}).get("utm")
            image = el.image
            if not image or not corners_utm or len(corners_utm) != 4:
                continue
            thermal_data = image.thermal_data
            elements.append(
                {
                    "image_id": image.id,
                    "filename": image.filename,
                    "thumbnail_url": image.thumbnail_url,
                    "corners_utm": corners_utm,
                    "temp_matrix_path": thermal_data.temp_matrix_path if thermal_data else None,
                }
            )
        maps_out.append({"id": ir_map.id, "bounds_utm": bounds_utm, "elements": elements})

    return {"maps": maps_out}
