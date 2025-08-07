import time
from typing import List
from fastapi import HTTPException
from sqlalchemy.orm import Session
from app.schemas.report import ReportOut
from app.services.odm import WebodmManager
from app.services.mapping.progress_updater import ProgressUpdater
from app.schemas.report import ProcessingSettings
from app.schemas.map import MapCreate
from app.crud import report as crud_report
from app.crud import map as map_crud
import logging

import billiard as multiprocessing
from billiard import Pool
from rasterio.transform import from_bounds
import psutil


import pyproj
import rasterio


import cv2
import os

from app.config import UPLOAD_DIR


logger = logging.getLogger(__name__)


def process_webODM(
    report_id: int,
    mapping_report_id: int,
    webODM_project_id: str,
    mapping_selection: dict,
    settings: ProcessingSettings,
    db: Session,
    progress_updater: ProgressUpdater,
    map_index: int,
):
    """
    Process the report using WebODM if enabled.
    """
    odm_manager = WebodmManager()
    logger.info(
        f"Processing WebODM with manager (active:{odm_manager.active}, url: {odm_manager.url})"
    )
    logger.info(f"WebODM project ID: {webODM_project_id}")

    if not odm_manager.check_connection():
        logger.error("WebODM is not reachable.")
        return  # raise HTTPException(status_code=503, detail="WebODM is not reachable")

    if not webODM_project_id:
        webODM_project_id = create_odm_project(report_id, db, odm_manager)
    elif not odm_manager.check_project_exists(webODM_project_id):
        if not odm_manager.check_connection():
            logger.error("WebODM is not reachable.")
            return
        logger.error(f"WebODM project {webODM_project_id} does not exist.")
        webODM_project_id = create_odm_project(report_id, db, odm_manager)

    if not webODM_project_id:
        logger.error(
            f"Failed to create or retrieve WebODM project for report {report_id}"
        )
        return

    # check in the settings if scaling is enabled
    if True:  # settings['odm_scaling']:
        paths = scale_images(
            mapping_selection["images"], report_id, 1024
        )  # settings.image_size
        logger.info("ODM Scaling is enabled, but not implemented yet.")
    else:
        paths = [image.url for image in mapping_selection["images"]]
        logger.info("ODM Scaling is disabled, using original images.")

    try:
        image_type = mapping_selection["type"]
        odm_full = settings["odm_full"]
        logger.info(
            f"Uploading and processing images for {image_type} with {len(paths)} images in project {webODM_project_id}"
        )
        task_id = odm_manager.upload_and_process_images(
            project_id=webODM_project_id,
            images=paths,
            odm_full=odm_full,
            image_type=image_type,
        )
    except Exception as e:
        logger.error(f"Failed to create task {image_type} for report {report_id}: {e}")
        return
    finally:
        # delete the proxy images if they were created
        proxy_path = UPLOAD_DIR / str(report_id) / "proxy"
        if os.path.exists(proxy_path):
            try:
                for file in os.listdir(proxy_path):
                    os.remove(os.path.join(proxy_path, file))
                os.rmdir(proxy_path)
            except Exception as e:
                logger.error(f"Error cleaning up report folder: {e}")
                return {"error": str(e)}

    if task_id:
        # ask for status of the task
        while True:
            task = odm_manager.get_task(project_id=webODM_project_id, task_id=task_id)
            if task is None:
                logger.error(
                    f"Failed to get status for task {image_type} in project {webODM_project_id}"
                )
                break

            task_status = task["status"]
            task_progress = task["running_progress"]

            progress_updater.update_progress_of_map(
                status="processing", progress=task_progress * 100
            )

            if task_status == 20 or task_status == 10:
                time.sleep(3)
            elif task_status == 30 or task_status == 50:
                logger.info(
                    f"Task {mapping_selection['type']} for report {report_id} is ended prematurely with status {task_status}"
                )
                return
            elif task_status == 40:
                break

        map_path = odm_manager.download_orthophoto(webODM_project_id, task_id, report_id)
        if map_path is None:
            logger.error(
                f"Failed to get results for task {mapping_selection['type']} in project {webODM_project_id}"
            )
            return
        else:
            bounds = get_bounds_from_geotiff(map_path)
            png_path = convert_geotiff_to_png(map_path)
            map_data = MapCreate(
                mapping_report_id=mapping_report_id,
                name=f"odm_{mapping_selection['type']}_{map_index}",
                url=str(png_path),
                odm=True,
                bounds=bounds,
            )
            logger.info(
                f"Creating map in database for report {report_id} with data: {map_data}"
            )
            map = map_crud.create(db, map_data)

        progress_updater.update_progress_of_map(status="processing", progress=100.0)
        return webODM_project_id


def summon_webODM_mapping_selections(mapping_selections):
    """
    Summon mapping tasks based on the mapping selection.
    """
    if not mapping_selections:
        logger.warning("No mapping selection provided.")
        return []

    tasks = []
    for selection in mapping_selections:
        # check if type is already in one of the tasks, if so concatinate the "images" list
        existing_task = next(
            (task for task in tasks if task["type"] == selection["type"]), None
        )
        if existing_task:
            existing_task["images"].extend(selection["images"])
        else:
            tasks.append(selection)
    logger.info(
        f"Summoned {len(tasks)} WebODM mapping tasks from {len(mapping_selections)} mapping selections."
    )
    return tasks


def create_odm_project(report_id: int, db: Session, odm_manager: WebodmManager):
    """
    Creates a webODM project for the report and saves the project ID in the report.
    """
    report = crud_report.get_short_report(db, report_id)
    if not report:
        logger.error(f"Report {report_id} not found")
        raise HTTPException(status_code=404, detail=f"Report {report_id} not found")

    report_title = report.title if report.title else f"Report {report_id}"
    report_description = (
        report.description if report.description else "No description provided"
    )

    mapping_report = report.mapping_report
    if not mapping_report:
        logger.error(f"Mapping report for report {report_id} not found")
        raise HTTPException(
            status_code=404, detail=f"Mapping report for report {report_id} not found"
        )

    # Create a new project
    project_name = f"Argus report: {report_title}"
    project_id = odm_manager.create_project(
        name=project_name, description=report_description
    )

    if not project_id:
        logger.error(f"Failed to create WebODM project for report {report_id}")
        raise HTTPException(status_code=500, detail="Failed to create WebODM project")

   

    crud_report.set_webODM_project_id(db, report.mapping_report.id, project_id)

    return project_id


def scale_images(images, report_id, proxy_size):
    proxy_path = UPLOAD_DIR / str(report_id) / "proxy"
    if not os.path.exists(proxy_path):
        os.mkdir(proxy_path)

    scaled_image_paths = []
    nmbr_of_processes = calculate_number_of_safely_usable_processes(images[0].url)
    if nmbr_of_processes < len(images):
        nmbr_of_processes = len(images)

    MAX_RETRIES = 3
    TIMEOUT_PER_ITEM = 3  # seconds
    params = [(img.url, proxy_path, proxy_size) for img in images]

    for attempt in range(MAX_RETRIES):
        logger.info(f"Attempt {attempt + 1} to calculate UTM corners")
        with Pool(processes=nmbr_of_processes) as pool:
            try:
                scaled_image_paths = process_with_timeouts_starmap(
                    pool, scale_image, params, TIMEOUT_PER_ITEM
                )
                break  # success
            except Exception as e:
                logger.error(f"Failure in starmap attempt {attempt + 1}: {e}")
                pool.terminate()
                pool.join()

        if attempt == MAX_RETRIES - 1:
            logger.error("Failed to generate map elements after all retries")
            raise TimeoutError("Giving up on calculate_utm_corners")

    print("scaling done")
    return scaled_image_paths

def calculate_number_of_safely_usable_processes(example_image_path):
    example_memory_usage = get_image_memory_usage(example_image_path)
    print('example_memory_usage: ', example_memory_usage, 'of image: ', example_image_path)
    available_memory = psutil.virtual_memory().available

    # Calculate the number of processes based on memory usage
    max_processes = multiprocessing.cpu_count()
    if max_processes > 8:
        max_processes = max_processes - 2
    elif max_processes > 2:
        max_processes -= 1
    #len(os.sched_getaffinity(0))
    if example_memory_usage == 0:
        print("Example memory usage is 0, cannot calculate safely usable processes.")
        return max_processes
    safely_usable_processes = min(max_processes, int(available_memory / example_memory_usage))
    print('safely_usable_processes: ', safely_usable_processes, 'with max_processes: ', max_processes, 'and available_memory: ', available_memory)
    return safely_usable_processes

def get_image_memory_usage(image_path):
    initial_memory = psutil.virtual_memory().used
    loaded_image = cv2.imread(image_path)
    final_memory = psutil.virtual_memory().used

    image_memory_usage = final_memory - initial_memory
    loaded_image = None

    return image_memory_usage


def process_with_timeouts_starmap(pool, func, params, timeout_per_item=5):
    results = []
    async_results = []

    for param in params:
        res = pool.apply_async(func, args=param)
        async_results.append(res)

    for i, res in enumerate(async_results):
        try:
            result = res.get(timeout=timeout_per_item)
            results.append(result)
        except TimeoutError:
            logger.warning(f"Timeout processing item {i} with params {params[i]}")
            results.append(None)  # or use params[i] or a custom error placeholder
        except Exception as e:
            logger.error(f"Error processing item {i} with params {params[i]}: {e}")
            results.append(None)  # or log/handle differently
    return results


def scale_image(load_path, destination_path, size):
    img = cv2.imread(os.path.abspath(load_path))

    scale_percent = size / img.shape[1]
    dim = (int(img.shape[1] * scale_percent), int(img.shape[0] * scale_percent))
    resized = cv2.resize(img, dim, interpolation=cv2.INTER_NEAREST)
    img = None

    scaled_image_path = os.path.join(destination_path, os.path.basename(load_path))
    cv2.imwrite(scaled_image_path, resized)
    resized = None
    os.system("exiftool -TagsFromFile " + load_path + " " + scaled_image_path)
    return scaled_image_path


def get_bounds_from_geotiff(geotiff_path):
    """Extracts the bounds from a GeoTIFF file."""
    with rasterio.open(geotiff_path) as src:
        utm_bounds = src.bounds

        utm_crs = src.crs
        logger.info("UTM bounds: %s", utm_bounds)
        logger.info("UTM crs: %s", utm_crs)

        transformer = pyproj.Transformer.from_crs(utm_crs, "EPSG:4326")
        top_left = transformer.transform(utm_bounds.left, utm_bounds.top)
        top_right = transformer.transform(utm_bounds.right, utm_bounds.top)
        bottom_right = transformer.transform(utm_bounds.right, utm_bounds.bottom)
        bottom_left = transformer.transform(utm_bounds.left, utm_bounds.bottom)

        bounds = {
            "gps": {
                "latitude_max": top_left[0],
                "latitude_min": bottom_left[0],
                "longitude_max": top_right[1],
                "longitude_min": top_left[1],
            },
            "utm": {
                "zone": utm_crs.to_string(),
                "hemisphere": "N" if utm_crs.to_string().endswith("N") else "S",
                "easting_max": utm_bounds.right,
                "easting_min": utm_bounds.left,
                "northing_max": utm_bounds.top,
                "northing_min": utm_bounds.bottom,
            },
            "corners": {
                "gps": [
                    [top_left[1], top_left[0]],
                    [top_right[1], top_right[0]],
                    [bottom_right[1], bottom_right[0]],
                    [bottom_left[1], bottom_left[0]],
                ],
                "utm": [
                    [utm_bounds.left, utm_bounds.top],
                    [utm_bounds.right, utm_bounds.top],
                    [utm_bounds.right, utm_bounds.bottom],
                    [utm_bounds.left, utm_bounds.bottom],
                ],
            },
        }
        logger.info(f"Bounds: {bounds}")
        return bounds


def convert_geotiff_to_png(geotiff_path):
    """Converts a GeoTIFF file to PNG format."""
    im = cv2.imread(geotiff_path, cv2.IMREAD_UNCHANGED)
    filename = os.path.basename(geotiff_path).replace(".tif", ".png")
    save_path = os.path.join(os.path.dirname(geotiff_path), filename)
    cv2.imwrite(save_path, im)
    return save_path
