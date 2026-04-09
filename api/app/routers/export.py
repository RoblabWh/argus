import json
import logging
import os
import shutil
import time
import zipfile
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

import app.crud.report as report_crud
from app.config import config
from app.database import get_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/export", tags=["Export"])


def _is_color_image(image) -> bool:
    return not image.thermal and not image.panoramic


def _build_coco(report, mapping_report) -> dict:
    color_images = [img for img in mapping_report.images if _is_color_image(img)]

    # Collect unique category names in sorted order → assign ids 1..N
    class_names = sorted({
        det.class_name
        for img in color_images
        for det in img.detections
    })
    category_id_map = {name: idx + 1 for idx, name in enumerate(class_names)}

    coco_images = [
        {
            "id": img.id,
            "file_name": f"images/{img.filename}",
            "width": img.width,
            "height": img.height,
        }
        for img in color_images
    ]

    annotations = []
    for img in color_images:
        for det in img.detections:
            bbox = det.bbox if det.bbox is not None else []
            area = bbox[2] * bbox[3] if len(bbox) == 4 else 0
            annotations.append({
                "id": det.id,
                "image_id": det.image_id,
                "category_id": category_id_map[det.class_name],
                "bbox": bbox,
                "area": area,
                "iscrowd": 0,
                "score": det.score,
                "manually_verified": det.manually_verified,
            })

    categories = [
        {"id": category_id_map[name], "name": name}
        for name in class_names
    ]

    return {
        "info": {
            "description": "Argus Research Export",
            "argus_version": "2",
            "report_id": report.report_id,
            "report_title": report.title,
        },
        "licenses": [],
        "images": coco_images,
        "annotations": annotations,
        "categories": categories,
    }


def _build_projection(report, mapping_report) -> dict:
    images_by_id = {img.id: img for img in mapping_report.images}

    maps_data = []
    for m in mapping_report.maps:
        map_filename = Path(m.url).name if m.url else None
        map_elements_data = []
        for elem in m.map_elements:
            img = images_by_id.get(elem.image_id)
            if img is None or not _is_color_image(img):
                continue
            if elem.corners is None:
                continue
            argus_filename = Path(img.url).name if img.url else img.filename
            map_elements_data.append({
                "image_id": img.id,
                "original_filename": img.filename,
                "argus_filename": argus_filename,
                "corners": elem.corners,
                "voronoi_gps": elem.voronoi_gps,
                "voronoi_image_px": elem.voronoi_image_px,
            })
        maps_data.append({
            "map_id": m.id,
            "map_filename": f"maps/{map_filename}" if map_filename else None,
            "map_elements": map_elements_data,
        })

    return {
        "argus_version": "2",
        "report_id": report.report_id,
        "report_title": report.title,
        "maps": maps_data,
    }


def _copy_map_files(mapping_report, maps_dir: Path) -> None:
    maps_dir.mkdir(parents=True, exist_ok=True)
    for m in mapping_report.maps:
        if not m.url:
            continue
        # map.url is stored as e.g. "reports_data/123/final_map_0_xxx.png" (relative to API workdir)
        src = Path(m.url)
        if not src.exists():
            logger.warning(f"Map file not found on disk: {m.url}")
            continue
        shutil.copy2(src, maps_dir / src.name)


def _copy_image_files(mapping_report, images_dir: Path) -> None:
    images_dir.mkdir(parents=True, exist_ok=True)
    for img in mapping_report.images:
        if not _is_color_image(img):
            continue
        src = Path(img.url)
        if not src.exists():
            logger.warning(f"Image file not found on disk: {img.url}")
            continue
        shutil.copy2(src, images_dir / img.filename)


def _cleanup_path(path: str) -> None:
    try:
        os.remove(path)
    except OSError:
        pass


@router.get("/r/{report_id}")
def export_research_data(
    report_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    include_images: bool = False,
):
    """
    Export detection annotations, map files, and projection metadata for a mapping report
    as a ZIP archive. Optionally include the original images.
    Only mapping reports are supported; reconstruction/pano reports return HTTP 422.
    """
    # Guard: report must exist and be a mapping report
    report = report_crud.get_short_report(db, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    if report.type != "mapping" or report.mapping_report is None:
        raise HTTPException(
            status_code=422,
            detail=f"Research export is only available for mapping reports. This report has type '{report.type}'.",
        )

    # Load full data (images + detections + maps + map_elements)
    full_report = report_crud.get_full_report(db, report_id)
    mapping_report = full_report.mapping_report

    # Create export folder
    ts = int(time.time())
    parent_dir = config.UPLOAD_DIR / str(report_id)
    export_dir = parent_dir / f"research_export_{ts}"
    export_dir.mkdir(parents=True, exist_ok=True)

    try:
        # annotations.json (COCO)
        coco = _build_coco(full_report, mapping_report)
        (export_dir / "annotations.json").write_text(
            json.dumps(coco, indent=2, ensure_ascii=False), encoding="utf-8"
        )

        # projection.json
        projection = _build_projection(full_report, mapping_report)
        (export_dir / "projection.json").write_text(
            json.dumps(projection, indent=2, ensure_ascii=False), encoding="utf-8"
        )

        # Map files
        _copy_map_files(mapping_report, export_dir / "maps")

        # Images (optional)
        if include_images:
            _copy_image_files(mapping_report, export_dir / "images")

        # ZIP
        zip_path = parent_dir / f"research_export_{ts}.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for file in sorted(export_dir.rglob("*")):
                if file.is_file():
                    zf.write(file, file.relative_to(export_dir))

    except Exception:
        shutil.rmtree(export_dir, ignore_errors=True)
        raise

    background_tasks.add_task(shutil.rmtree, str(export_dir), True)
    background_tasks.add_task(_cleanup_path, str(zip_path))

    return FileResponse(
        path=str(zip_path),
        media_type="application/zip",
        filename=f"export_{report_id}.zip",
        background=background_tasks,
    )
