from fastapi import APIRouter, UploadFile, File, Depends
from sqlalchemy.orm import Session
from uuid import uuid4
from pathlib import Path
import shutil
from datetime import datetime, timezone
from PIL import Image

from app.config import UPLOAD_DIR

import app.crud.images as crud_image
import app.crud.report as crud_report

import app.services.image_metadata_extraction as metadata_extraction


router = APIRouter()
UPLOAD_DIR.mkdir(exist_ok=True)
ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png"} #maybe later add support for tiff, bmp, webp, etc.



def process_image(report_id: int, file: UploadFile, db: Session):
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
        
        mapping_report_id = check_mapping_report(report_id, db)
        
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

