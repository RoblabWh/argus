from fastapi import APIRouter, UploadFile, File, Depends
from sqlalchemy.orm import Session
from uuid import uuid4
from pathlib import Path
import shutil
from datetime import datetime, timezone
from PIL import Image
import logging

from app.config import config
UPLOAD_DIR = Path(config.UPLOAD_DIR)

import app.crud.images as crud_image
import app.crud.report as crud_report

import app.services.image_metadata_extraction as metadata_extraction

logger = logging.getLogger(__name__)

router = APIRouter()
UPLOAD_DIR.mkdir(exist_ok=True)
ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png"} #maybe later add support for tiff, bmp, webp, etc.



def process_image(report_id: int, file: UploadFile, mapping_report_id: int, db: Session):
    """Processes a single image file, saving it to the filesystem and storing metadata in the database.
    Args:
        file (UploadFile): The uploaded image file.
        db (Session): Database session dependency.
    Returns:
        dict: A dictionary containing the original filename and the filename it was stored as.
    """

   
    try:
        if not file.filename:
            return {
                "img_object": None,
                "filename": "None",
                "status": "error",
                "error": "Filename not provided"
            }
    
        if not file.filename.split(".")[-1].lower() in ALLOWED_EXTENSIONS:
            return {
                "img_object": None, 
                "filename": file.filename,
                "status": "error",
                "error": "Unsupported file type"
            }
                
        file.file.seek(0)

        # Save file
        og_filename = file.filename
        ext = file.filename.split(".")[-1]
        filename = f"{uuid4()}.{ext}"
        file_path = UPLOAD_DIR / str(report_id) / filename

        # Ensure the directory exists
        file_path.parent.mkdir(parents=True, exist_ok=True)

        with file_path.open("wb") as f:
            shutil.copyfileobj(file.file, f)


        metadata = metadata_extraction.extract_image_metadata(file_path)

        # Create a thumbnail (placeholder logic, replace with actual thumbnail creation)
        thumbnail_path = save_thumbnail(file_path, file)
        

        data = {
            "mapping_report_id": mapping_report_id,
            "filename": og_filename,
            "url": str(file_path),
            "thumbnail_url": str(thumbnail_path),
            "created_at": metadata["created_at"],
            "uploaded_at": datetime.now(timezone.utc).isoformat(),
            "width": metadata["width"],
            "height": metadata["height"],
            "camera_model": metadata["camera_model"],
            "mappable": metadata["mappable"],
            "panoramic": metadata["panoramic"],
            "thermal": metadata["thermal"],
        }

        try:
            data["coord"] = metadata["coord"]
        except KeyError:
            #print("No coordinate data found in metadata.", flush=True)
            pass
            

        # Store metadata in the database
        img = crud_image.create(db, data)
        if metadata['mappable']:
            mapping_data = metadata.get("mapping_data", {})
            mapping_data["image_id"] = img.id
            img = crud_image.create_mapping_data(db, mapping_data)
        else:
            img = crud_image.get_full_image(db, img.id)
            


        return {
            "image_object": img,
            "status": "success",
        }
    
    except Exception as e:
        print(f"Error processing file {file.filename}: {e}")

        # delete possibly created files
        if file_path:
            if file_path.exists():
                file_path.unlink()

        if thumbnail_path:
            if thumbnail_path.exists():
                thumbnail_path.unlink()

        return {
            "image_object": None,
            "filename": file.filename,
            "status": "error",
            "error": str(e)
        }



def extract_metadata(file_path: Path) -> dict:
    """Extracts metadata from the image file.
    Args:
        file_path (Path): The path to the image file.
    Returns:
        dict: A dictionary containing extracted metadata.
    """
    #todo: Implement actual metadata extraction logic
    # This is a placeholder implementation. Replace with actual metadata extraction logic.

    data = {
        "created_at": datetime.now(timezone.utc).isoformat(),  # Placeholder for actual creation time
        "width": 1920,
        "height": 1080,
        # "coord": {"lat": 0.0, "lon": 0.0}, # if available
        "camera_model": "Dummy Camera",
        "mappable": True, # check if image seems mappable # if so extract mapping data during preprocessing
        "panoramic": False, # check if image is panoramic
        "thermal": False, # check if image is thermal # if so extract thermal data during preprocessing
    }

    return data



def save_thumbnail(file_path: Path, file: UploadFile) -> Path:
    """Saves a thumbnail for the image file.
    Args:
        file_path (Path): The path to the original image file.
        file (UploadFile): The uploaded image file.
    Returns:
        Path: The path to the saved thumbnail image.
    """
    thumb_dir = file_path.parent / "thumbnails"
    thumb_dir.mkdir(parents=True, exist_ok=True)
    thumb_path = thumb_dir / file_path.name

    with Image.open(file_path) as img:
        img.thumbnail((300, 300))
        img.save(thumb_path, "JPEG")

    return thumb_path



def check_mapping_report(report_id: int, db: Session) -> int:
    """Checks if the report exists or creates it and returns its ID.
    Args:
        report_id (int): The ID of the report to check.
        db (Session): Database session dependency.
    Returns:
        int: The ID of the mapping report.
    """
    # Check if the report exists
    report = crud_report.get_full_report(db, report_id)
    mapping_report = report.mapping_report if report else None
    if not mapping_report or mapping_report.id is None:
        mapping_report = crud_report.create_mapping_report(db, report_id)
    
    return mapping_report.id


def reread_image_metadata(images, db: Session, progress_updater=None):
    """Re-extract metadata from image files and update DB records.

    Preserves identity fields (id, mapping_report_id, filename, url,
    thumbnail_url, uploaded_at) but refreshes everything derived from
    EXIF metadata: dimensions, coordinates, camera model, orientation,
    mappable/thermal/panoramic flags, and MappingData.
    """
    total = len(images)
    updated = 0
    for i, image in enumerate(images):
        try:
            metadata = metadata_extraction.extract_image_metadata(image.url)
        except Exception as e:
            logger.warning(f"Failed to re-read metadata for image {image.id}: {e}")
            continue

        image.width = metadata["width"]
        image.height = metadata["height"]
        image.camera_model = metadata["camera_model"]
        image.mappable = metadata["mappable"]
        image.panoramic = metadata["panoramic"]
        image.thermal = metadata["thermal"]
        image.created_at = metadata["created_at"]
        image.preprocessed = False
        if metadata.get("coord"):
            image.coord = metadata["coord"]

        # Delete old MappingData and recreate from fresh extraction
        crud_image.delete_mapping_data(db, image.id)
        if metadata["mappable"]:
            mapping_data = metadata.get("mapping_data", {})
            mapping_data["image_id"] = image.id
            crud_image.create_mapping_data(db, mapping_data)

        updated += 1
        if progress_updater:
            progress_updater.update_progress(
                "preprocessing", (i + 1) / total * 100
            )

    db.commit()
    logger.info(f"Re-read metadata for {updated}/{total} images")
