import os
from pathlib import Path
from app.config import UPLOAD_DIR

UPLOAD_DIR.mkdir(exist_ok=True)

#delete every file and directory in a folder named with id
def cleanup_report_folder(report_id: str):
    report_folder = UPLOAD_DIR / str(report_id)

    if not report_folder.exists():
        return {"message": "Report folder does not exist"}
    
    try:
        recursive_cleanup(report_folder)
        report_folder.rmdir()

        return {"message": "Report folder cleaned up successfully"}
    except Exception as e:
        return {"error": str(e)}
    

def recursive_cleanup(path: Path):
    """
    Recursively delete all files and directories in the given path.
    """
    if not path.exists():
        return {"message": "Path does not exist"}
    
    try:
        for item in path.iterdir():
            if item.is_file():
                item.unlink()
            elif item.is_dir():
                recursive_cleanup(item)
                item.rmdir()  # Remove the directory after its contents are deleted
        return {"message": "Cleanup completed successfully"}
    except Exception as e:
        return {"error": str(e)}
    



def delete_image_file(image):
    """Deletes the image file from the filesystem.
    Args:
        image (models.Image): The image object containing the file path.
    Returns:
        bool: True if the file was deleted successfully, False otherwise.
    """
    try:
        file_path = Path(image.url)
        if not delete_file(file_path):
            print(f"Failed to delete image file {image.url}", flush=True)
            return False
        thumbnail_path = Path(image.thumbnail_url)
        if not delete_file(thumbnail_path):
            print(f"Failed to delete thumbnail file {image.thumbnail_url}", flush=True)
            return False
        return True
    except Exception as e:
        print(f"Error deleting image file {image.url}: {e}", flush=True)
        return False
    


def delete_file(path):
    """Deletes a file from the filesystem.
    Args:
        path (str): The path to the file to delete.
    Returns:
        bool: True if the file was deleted successfully, False otherwise.
    """
    try:
        file_path = Path(path)
        if file_path.exists():
            file_path.unlink()
            return True
        else:
            print(f"File {file_path} does not exist.", flush=True)
            return True
    except Exception as e:
        print(f"Error deleting file {file_path}: {e}", flush=True)
        return False