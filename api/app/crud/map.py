from sqlalchemy.orm import Session, joinedload
from datetime import datetime
import redis

from app import models
from app.schemas.map import MapCreate, MapUpdate
from app.schemas.map import MapElementCreate, MapElementUpdate

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
        **data.dict(),
        created_at=datetime.utcnow(),
    )
    db.add(new_map)
    db.commit()
    db.refresh(new_map)
    return new_map

def delete(db: Session, map_id: int):
    map_to_delete = db.query(models.Map).filter(models.Map.id == map_id).first()
    if map_to_delete:
        db.delete(map_to_delete)
        db.commit()
        return True
    return False

def create_multiple_map_elements(db: Session, map_id: int, elements: list[MapElementCreate]):
    map_elements = [models.MapElement(**element.dict()) for element in elements]
    db.add_all(map_elements)
    db.commit()
    return map_elements
