import json
import logging
import os
import shutil
import tempfile
import zipfile
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from tempfile import SpooledTemporaryFile

from sqlalchemy.orm import Session

from app import models
from app.config import config
from app.crud.report import get_full_report
from app.services.cleanup import cleanup_report_folder

logger = logging.getLogger(__name__)

UPLOAD_DIR = Path(config.UPLOAD_DIR)
EXPORT_VERSION = 1


def export_report(db: Session, report_id: int):
    """Export a report and all its data/files as a ZIP archive.

    Returns (file_obj, filename) where file_obj is a seeked-to-0
    SpooledTemporaryFile containing the ZIP.
    """
    report = get_full_report(db, report_id)
    if not report:
        return None, None

    mr = report.mapping_report
    pr = report.pano_report

    # Build export-id mappings
    image_id_map = {}  # db id -> export_id
    map_id_map = {}
    if mr:
        for i, img in enumerate(mr.images):
            image_id_map[img.id] = f"img{i}"
        for i, mp in enumerate(mr.maps):
            map_id_map[mp.id] = f"map{i}"

    manifest = _build_manifest(report, mr, pr, image_id_map, map_id_map)
    files_to_add = _collect_files(mr, manifest)

    # Write ZIP
    slug = _slugify(report.title) if report.title else "export"
    filename = f"argus_report_{report_id}_{slug}.zip"

    spool = SpooledTemporaryFile(max_size=50 * 1024 * 1024)
    with zipfile.ZipFile(spool, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("manifest.json", json.dumps(manifest, indent=2, default=str))
        for disk_path, zip_path in files_to_add:
            if os.path.isfile(disk_path):
                zf.write(disk_path, zip_path)
            else:
                logger.warning(f"File not found, skipping: {disk_path}")

    spool.seek(0)
    return spool, filename


def import_report(db: Session, zip_path: str, group_id: int):
    """Import a report from a ZIP archive into the given group.

    Returns the newly created Report ORM object.
    """
    with zipfile.ZipFile(zip_path, "r") as zf:
        raw = zf.read("manifest.json")
        manifest = json.loads(raw)

    _validate_manifest(manifest)

    new_report = None
    new_report_id = None
    try:
        now = datetime.utcnow()
        m_report = manifest["report"]
        has_maps = bool(manifest.get("maps"))

        # 1. Report
        new_report = models.Report(
            group_id=group_id,
            type=m_report.get("type", "unset"),
            title=m_report.get("title", "Imported Report"),
            description=m_report.get("description", ""),
            status="completed" if has_maps else "unprocessed",
            progress=100.0 if has_maps else 0.0,
            processing_duration=m_report.get("processing_duration"),
            requires_reprocessing=False,
            auto_description=m_report.get("auto_description"),
            created_at=now,
            updated_at=now,
        )
        db.add(new_report)
        db.flush()
        new_report_id = new_report.report_id

        # Create report directory
        report_dir = UPLOAD_DIR / str(new_report_id)
        report_dir.mkdir(parents=True, exist_ok=True)
        (report_dir / "thumbnails").mkdir(exist_ok=True)

        # 2. MappingReport
        new_mr = None
        m_mr = manifest.get("mapping_report")
        if m_mr:
            new_mr = models.MappingReport(
                report_id=new_report_id,
                flight_timestamp=_parse_dt(m_mr.get("flight_timestamp")),
                coord=m_mr.get("coord"),
                address=m_mr.get("address"),
                flight_duration=m_mr.get("flight_duration"),
                flight_height=m_mr.get("flight_height"),
                covered_area=m_mr.get("covered_area"),
                uav=m_mr.get("uav", "Unknown"),
                image_count=m_mr.get("image_count", 0),
                webodm_project_id=None,
            )
            db.add(new_mr)
            db.flush()

        # 3. PanoReport
        m_pr = manifest.get("pano_report")
        if m_pr:
            new_pr = models.PanoReport(
                report_id=new_report_id,
                video_duration=m_pr.get("video_duration"),
            )
            db.add(new_pr)
            db.flush()

        # 4. Images
        image_id_map = {}  # export_id -> new db id
        for m_img in manifest.get("images", []):
            export_id = m_img["_export_id"]
            img = models.Image(
                mapping_report_id=new_mr.id if new_mr else None,
                filename=m_img.get("filename"),
                url=m_img.get("url", ""),  # will be updated after file extraction
                thumbnail_url=m_img.get("thumbnail_url", ""),
                created_at=_parse_dt(m_img.get("created_at")),
                uploaded_at=_parse_dt(m_img.get("uploaded_at")),
                width=m_img.get("width"),
                height=m_img.get("height"),
                coord=m_img.get("coord"),
                camera_model=m_img.get("camera_model"),
                preprocessed=m_img.get("preprocessed", False),
                mappable=m_img.get("mappable", False),
                panoramic=m_img.get("panoramic", False),
                thermal=m_img.get("thermal", False),
            )
            db.add(img)
            db.flush()
            image_id_map[export_id] = img.id

        # 5. MappingData
        for m_img in manifest.get("images", []):
            md = m_img.get("mapping_data")
            if not md:
                continue
            new_image_id = image_id_map[m_img["_export_id"]]
            mapping_data = models.MappingData(
                image_id=new_image_id,
                fov=md.get("fov"),
                rel_altitude=md.get("rel_altitude", 100.0),
                rel_altitude_method=md.get("rel_altitude_method", "exif"),
                altitude=md.get("altitude"),
                cam_pitch=md.get("cam_pitch"),
                cam_roll=md.get("cam_roll"),
                cam_yaw=md.get("cam_yaw"),
                uav_pitch=md.get("uav_pitch"),
                uav_roll=md.get("uav_roll"),
                uav_yaw=md.get("uav_yaw"),
            )
            db.add(mapping_data)

        # 6. ThermalData
        for m_img in manifest.get("images", []):
            td = m_img.get("thermal_data")
            if not td:
                continue
            new_image_id = image_id_map[m_img["_export_id"]]
            counterpart_id = None
            if td.get("counterpart_export_id"):
                counterpart_id = image_id_map.get(td["counterpart_export_id"])
            thermal_data = models.ThermalData(
                image_id=new_image_id,
                counterpart_id=counterpart_id,
                counterpart_scale=td.get("counterpart_scale", 1.1),
                min_temp=td.get("min_temp"),
                max_temp=td.get("max_temp"),
                temp_matrix_path=td.get("temp_matrix_path", ""),  # updated after extraction
                temp_embedded=td.get("temp_embedded", True),
                temp_unit=td.get("temp_unit", "C"),
                lut_name=td.get("lut_name"),
            )
            db.add(thermal_data)

        # 7. Detections
        for m_img in manifest.get("images", []):
            for det in m_img.get("detections", []):
                new_image_id = image_id_map[m_img["_export_id"]]
                detection = models.Detection(
                    image_id=new_image_id,
                    class_name=det.get("class_name"),
                    score=det.get("score"),
                    bbox=det.get("bbox"),
                    manually_verified=det.get("manually_verified", False),
                    coord=det.get("coord"),
                )
                db.add(detection)

        # 8. Maps
        map_id_map = {}  # export_id -> new db id
        for m_map in manifest.get("maps", []):
            export_id = m_map["_export_id"]
            new_map = models.Map(
                mapping_report_id=new_mr.id if new_mr else None,
                name=m_map.get("name"),
                url=m_map.get("url", ""),  # updated after extraction
                created_at=_parse_dt(m_map.get("created_at")),
                odm=m_map.get("odm", False),
                bounds=m_map.get("bounds"),
            )
            db.add(new_map)
            db.flush()
            map_id_map[export_id] = new_map.id

        # 9. MapElements
        for m_map in manifest.get("maps", []):
            new_map_id = map_id_map[m_map["_export_id"]]
            for me in m_map.get("map_elements", []):
                img_export_id = me.get("image_export_id")
                new_image_id = image_id_map.get(img_export_id) if img_export_id else None
                map_element = models.MapElement(
                    map_id=new_map_id,
                    image_id=new_image_id,
                    index=me.get("index"),
                    coord=me.get("coord"),
                    corners=me.get("corners"),
                    px_coord=me.get("px_coord"),
                    px_corners=me.get("px_corners"),
                )
                db.add(map_element)

        # 10. Weather
        for m_w in manifest.get("weather", []):
            weather = models.Weather(
                mapping_report_id=new_mr.id if new_mr else None,
                open_weather_id=m_w.get("open_weather_id"),
                description=m_w.get("description"),
                temperature=m_w.get("temperature"),
                humidity=m_w.get("humidity"),
                pressure=m_w.get("pressure"),
                wind_speed=m_w.get("wind_speed"),
                wind_dir_deg=m_w.get("wind_dir_deg"),
                visibility=m_w.get("visibility"),
                timestamp=_parse_dt(m_w.get("timestamp")),
            )
            db.add(weather)

        db.flush()

        # Extract files from ZIP and update paths
        _extract_and_update_paths(db, zip_path, manifest, new_report_id, image_id_map, map_id_map)

        db.commit()
        db.refresh(new_report)
        return new_report

    except Exception:
        db.rollback()
        if new_report_id:
            try:
                cleanup_report_folder(new_report_id)
            except Exception as cleanup_err:
                logger.error(f"Failed to cleanup after import error: {cleanup_err}")
        raise


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _build_manifest(report, mr, pr, image_id_map, map_id_map):
    manifest = {
        "argus_export_version": EXPORT_VERSION,
        "exported_at": datetime.utcnow().isoformat(),
        "report": {
            "title": report.title,
            "description": report.description,
            "type": report.type,
            "auto_description": report.auto_description,
            "created_at": _dt_str(report.created_at),
            "processing_duration": report.processing_duration,
        },
    }

    if mr:
        manifest["mapping_report"] = {
            "flight_timestamp": _dt_str(mr.flight_timestamp),
            "coord": mr.coord,
            "address": mr.address,
            "flight_duration": mr.flight_duration,
            "flight_height": mr.flight_height,
            "covered_area": mr.covered_area,
            "uav": mr.uav,
            "image_count": mr.image_count,
        }
    else:
        manifest["mapping_report"] = None

    if pr:
        manifest["pano_report"] = {
            "video_duration": pr.video_duration,
        }
    else:
        manifest["pano_report"] = None

    # Images
    used_image_filenames = defaultdict(int)
    images_list = []
    if mr:
        for img in mr.images:
            export_id = image_id_map[img.id]
            img_zip_path, thumb_zip_path = _image_zip_paths(img, used_image_filenames)

            img_data = {
                "_export_id": export_id,
                "filename": img.filename,
                "url": img_zip_path,
                "thumbnail_url": thumb_zip_path,
                "created_at": _dt_str(img.created_at),
                "uploaded_at": _dt_str(img.uploaded_at),
                "width": img.width,
                "height": img.height,
                "coord": img.coord,
                "camera_model": img.camera_model,
                "preprocessed": img.preprocessed,
                "mappable": img.mappable,
                "panoramic": img.panoramic,
                "thermal": img.thermal,
            }

            # MappingData
            if img.mapping_data:
                md = img.mapping_data
                img_data["mapping_data"] = {
                    "fov": md.fov,
                    "rel_altitude": md.rel_altitude,
                    "rel_altitude_method": md.rel_altitude_method,
                    "altitude": md.altitude,
                    "cam_pitch": md.cam_pitch,
                    "cam_roll": md.cam_roll,
                    "cam_yaw": md.cam_yaw,
                    "uav_pitch": md.uav_pitch,
                    "uav_roll": md.uav_roll,
                    "uav_yaw": md.uav_yaw,
                }
            else:
                img_data["mapping_data"] = None

            # ThermalData
            if img.thermal_data:
                td = img.thermal_data
                npy_zip_path = None
                if td.temp_matrix_path and os.path.isfile(td.temp_matrix_path):
                    npy_basename = os.path.basename(td.temp_matrix_path)
                    npy_zip_path = f"thermal/{npy_basename}"
                img_data["thermal_data"] = {
                    "counterpart_export_id": image_id_map.get(td.counterpart_id),
                    "counterpart_scale": td.counterpart_scale,
                    "min_temp": td.min_temp,
                    "max_temp": td.max_temp,
                    "temp_matrix_path": npy_zip_path,
                    "temp_embedded": td.temp_embedded,
                    "temp_unit": td.temp_unit,
                    "lut_name": td.lut_name,
                }
            else:
                img_data["thermal_data"] = None

            # Detections
            img_data["detections"] = [
                {
                    "class_name": d.class_name,
                    "score": d.score,
                    "bbox": d.bbox,
                    "manually_verified": d.manually_verified,
                    "coord": d.coord,
                }
                for d in (img.detections or [])
            ]

            images_list.append(img_data)

    manifest["images"] = images_list

    # Maps
    used_map_filenames = defaultdict(int)
    maps_list = []
    if mr:
        for mp in mr.maps:
            export_id = map_id_map[mp.id]
            map_zip_path = None
            if mp.url and os.path.isfile(mp.url):
                basename = os.path.basename(mp.url)
                count = used_map_filenames[basename]
                used_map_filenames[basename] += 1
                if count > 0:
                    name, ext = os.path.splitext(basename)
                    basename = f"{name}_{count + 1}{ext}"
                map_zip_path = f"maps/{basename}"

            map_data = {
                "_export_id": export_id,
                "name": mp.name,
                "url": map_zip_path,
                "created_at": _dt_str(mp.created_at),
                "odm": mp.odm,
                "bounds": mp.bounds,
                "map_elements": [],
            }

            for me in (mp.map_elements or []):
                map_data["map_elements"].append({
                    "image_export_id": image_id_map.get(me.image_id),
                    "index": me.index,
                    "coord": me.coord,
                    "corners": me.corners,
                    "px_coord": me.px_coord,
                    "px_corners": me.px_corners,
                })

            maps_list.append(map_data)

    manifest["maps"] = maps_list

    # Weather
    weather_list = []
    if mr:
        for w in (mr.weather or []):
            weather_list.append({
                "open_weather_id": w.open_weather_id,
                "description": w.description,
                "temperature": w.temperature,
                "humidity": w.humidity,
                "pressure": w.pressure,
                "wind_speed": w.wind_speed,
                "wind_dir_deg": w.wind_dir_deg,
                "visibility": w.visibility,
                "timestamp": _dt_str(w.timestamp),
            })

    manifest["weather"] = weather_list

    return manifest


def _collect_files(mr, manifest):
    """Return list of (disk_path, zip_path) tuples from the manifest."""
    files = []
    if not mr:
        return files

    for m_img in manifest.get("images", []):
        # Find the original image on disk by looking up the ORM image
        # We use the mapping report's images to find disk paths
        export_id = m_img["_export_id"]
        idx = int(export_id.replace("img", ""))
        img = mr.images[idx]

        if m_img.get("url") and img.url and os.path.isfile(img.url):
            files.append((img.url, m_img["url"]))
        if m_img.get("thumbnail_url") and img.thumbnail_url and os.path.isfile(img.thumbnail_url):
            files.append((img.thumbnail_url, m_img["thumbnail_url"]))

        td = m_img.get("thermal_data")
        if td and td.get("temp_matrix_path") and img.thermal_data:
            disk_path = img.thermal_data.temp_matrix_path
            if disk_path and os.path.isfile(disk_path):
                files.append((disk_path, td["temp_matrix_path"]))

    for m_map in manifest.get("maps", []):
        export_id = m_map["_export_id"]
        idx = int(export_id.replace("map", ""))
        mp = mr.maps[idx]
        if m_map.get("url") and mp.url and os.path.isfile(mp.url):
            files.append((mp.url, m_map["url"]))

    return files


def _extract_and_update_paths(db, zip_path, manifest, new_report_id, image_id_map, map_id_map):
    """Extract files from ZIP into reports_data/{new_report_id}/ and update DB paths."""
    report_dir = UPLOAD_DIR / str(new_report_id)

    with zipfile.ZipFile(zip_path, "r") as zf:
        for m_img in manifest.get("images", []):
            export_id = m_img["_export_id"]
            new_image_id = image_id_map[export_id]
            img_obj = db.query(models.Image).filter(models.Image.id == new_image_id).first()

            # Extract image file
            if m_img.get("url") and m_img["url"] in zf.namelist():
                basename = os.path.basename(m_img["url"])
                dest = report_dir / basename
                _extract_member(zf, m_img["url"], dest)
                img_obj.url = str(dest)
            else:
                img_obj.url = None

            # Extract thumbnail
            if m_img.get("thumbnail_url") and m_img["thumbnail_url"] in zf.namelist():
                basename = os.path.basename(m_img["thumbnail_url"])
                dest = report_dir / "thumbnails" / basename
                _extract_member(zf, m_img["thumbnail_url"], dest)
                img_obj.thumbnail_url = str(dest)
            else:
                img_obj.thumbnail_url = None

            # Extract thermal .npy
            td = m_img.get("thermal_data")
            if td and td.get("temp_matrix_path") and td["temp_matrix_path"] in zf.namelist():
                td_obj = db.query(models.ThermalData).filter(
                    models.ThermalData.image_id == new_image_id
                ).first()
                if td_obj:
                    basename = os.path.basename(td["temp_matrix_path"])
                    dest = report_dir / basename
                    _extract_member(zf, td["temp_matrix_path"], dest)
                    td_obj.temp_matrix_path = str(dest)

        for m_map in manifest.get("maps", []):
            export_id = m_map["_export_id"]
            new_map_id = map_id_map[export_id]
            map_obj = db.query(models.Map).filter(models.Map.id == new_map_id).first()

            if m_map.get("url") and m_map["url"] in zf.namelist():
                basename = os.path.basename(m_map["url"])
                dest = report_dir / basename
                _extract_member(zf, m_map["url"], dest)
                map_obj.url = str(dest)
            else:
                map_obj.url = None


def _extract_member(zf, member_name, dest_path):
    """Safely extract a single ZIP member to a destination path."""
    dest_path = Path(dest_path)
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    with zf.open(member_name) as src, open(dest_path, "wb") as dst:
        shutil.copyfileobj(src, dst)


def _image_zip_paths(img, used_filenames):
    """Determine zip-internal paths for an image and its thumbnail, handling duplicate names."""
    img_zip_path = None
    thumb_zip_path = None

    if img.url and os.path.isfile(img.url):
        basename = os.path.basename(img.url)
        count = used_filenames[basename]
        used_filenames[basename] += 1
        if count > 0:
            name, ext = os.path.splitext(basename)
            basename = f"{name}_{count + 1}{ext}"
        img_zip_path = f"images/{basename}"

    if img.thumbnail_url and os.path.isfile(img.thumbnail_url):
        basename = os.path.basename(img.thumbnail_url)
        count = used_filenames[basename]
        used_filenames[basename] += 1
        if count > 0:
            name, ext = os.path.splitext(basename)
            basename = f"{name}_{count + 1}{ext}"
        thumb_zip_path = f"thumbnails/{basename}"

    return img_zip_path, thumb_zip_path


def _validate_manifest(manifest):
    """Validate the manifest dict. Raises ValueError on problems."""
    if not isinstance(manifest, dict):
        raise ValueError("Invalid manifest: not a JSON object")

    version = manifest.get("argus_export_version")
    if version is None:
        raise ValueError("Invalid manifest: missing argus_export_version")
    if version > EXPORT_VERSION:
        raise ValueError(
            f"Unsupported export version {version} (max supported: {EXPORT_VERSION})"
        )

    if "report" not in manifest:
        raise ValueError("Invalid manifest: missing 'report' field")


def _slugify(text):
    """Simple slugify for filenames."""
    if not text:
        return "export"
    slug = "".join(c if c.isalnum() or c in "-_ " else "" for c in text)
    return slug.strip().replace(" ", "_")[:50]


def _dt_str(dt):
    """Convert datetime to ISO string or None."""
    if dt is None:
        return None
    if isinstance(dt, str):
        return dt
    return dt.isoformat()


def _parse_dt(val):
    """Parse an ISO datetime string, or return None."""
    if val is None:
        return None
    if isinstance(val, datetime):
        return val
    try:
        return datetime.fromisoformat(val)
    except (ValueError, TypeError):
        return None
