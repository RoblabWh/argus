"""
Situation report ("Lagebild") generation for mapping reports.

Drop-in replacement for `image_describer.py`: exposes the same
`start_description_process(report_id, db)` entry point, writes the same Redis
keys / SSE events and stores the result in `Report.auto_description`. Switching
between the two services is a single import in `routers/reports.py`.

Instead of describing every image and summarising the summaries, this service
builds a structured situation report loosely following the German Lagebild
scheme (Allgemeine Lage / Eigene Lage / Gefahren- und Schadenslage):

1. collect flight metadata, weather, detections and thermal hotspots from the DB
2. pick a spatially spread subset of images (hotspots / detections first)
3. extract structured findings per image (one call per image, in parallel)
4. optionally look at the generated orthophoto for the global layout
5. let the same model synthesise the report sections from findings + metadata
6. render the report; hard numbers come from the DB, not from the LLM

A single multimodal model handles both vision and text, so no model swap is
needed. The model is always unloaded afterwards to free VRAM for other workers.
"""

import base64
import logging
import math
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from io import BytesIO
from typing import Literal, Optional

import ollama
import redis
from PIL import Image, ImageOps
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy.orm import Session

import app.crud.report as report_crud  # must be imported before crud.images (circular import via services.cleanup)
import app.crud.images as images_crud
import app.services.events as events_service
from app.database import get_db
from app.services.celery_app import celery_app

REDIS_PORT = os.getenv("REDIS_PORT", 6379)
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
OLLAMA_PORT = os.getenv("OLLAMA_PORT", "11434")
OLLAMA_HOST = os.getenv("OLLAMA_HOST_URL", f"http://argusII_ollama:{OLLAMA_PORT}")

MODEL = os.getenv("SITUATION_REPORT_MODEL", "qwen3-vl:8b-instruct")
REPORT_LANGUAGE = os.getenv("SITUATION_REPORT_LANGUAGE", "en")

# Detail presets (chosen per run in the UI): how many images go through the vision model.
FAST_MAX_IMAGES = int(os.getenv("SITUATION_REPORT_MAX_IMAGES", 16))
DETAIL_LEVELS = ("fast", "medium", "detailed")  # fast: FAST_MAX_IMAGES, medium: every 2nd image, detailed: all
CHUNK_SIZE = 20             # above this many findings, summarise chunks first so the synthesis fits NUM_CTX
PARALLEL_REQUESTS = int(os.getenv("SITUATION_REPORT_PARALLEL", 2))  # keep in sync with OLLAMA_NUM_PARALLEL
IMAGE_MAX_SIDE = 1024       # px, long side sent to the model
MAP_MAX_SIDE = 1536         # px, long side of the orthophoto overview
# One context size for every call: changing num_ctx between calls makes Ollama reload the model.
NUM_CTX = 12288
REQUEST_TIMEOUT = 300.0     # seconds per model call
KEEP_ALIVE = "10m"          # keep the model warm between calls of one run
HOTSPOT_TEMP_C = 60.0       # thermal max temperature that counts as a hotspot
DETECTION_SCORE_THRESHOLD = 0.2  # same default as the frontend's DetectionCard thresholds
FIRE_CLASSES = {"fire", "smoke"}
# Sampling as recommended for Qwen3-VL instruct. Near-greedy sampling (temperature ~0) makes
# the model fall into repetition loops on longer outputs; num_predict is a hard stop on top.
MODEL_OPTIONS = {"temperature": 0.7, "top_p": 0.8, "top_k": 20, "presence_penalty": 1.5,
                 "num_ctx": NUM_CTX, "num_predict": 1024}
SYNTHESIS_OPTIONS = {**MODEL_OPTIONS, "temperature": 0.5, "num_predict": 2048}
JSON_RETRIES = 1            # extra attempts when the model returns invalid / truncated JSON

LANGUAGE_NAMES = {"en": "English", "de": "German"}

LABELS = {
    "en": {
        "title": "SITUATION REPORT",
        "generated": "Generated {time} UTC with {model} · {detail} · {analysed} of {total} images analysed",
        "detail_names": {"fast": "fast", "medium": "medium", "detailed": "detailed"},
        "general": "1. GENERAL SITUATION",
        "own": "2. OWN SITUATION (UAV RECONNAISSANCE)",
        "hazards": "3. HAZARD AND DAMAGE SITUATION",
        "open": "4. OPEN POINTS / LIMITATIONS",
        "location": "Location",
        "flight_time": "Time of flight",
        "weather": "Weather",
        "uav": "UAV",
        "duration": "Flight duration",
        "height": "Avg. flight height",
        "area": "Covered area",
        "images": "Images",
        "detections": "Detections (AI)",
        "det_value": "{counts} – estimated distinct objects ({method}) from {raw} boxes in overlapping images",
        "det_methods": {"reid": "re-ID", "clipped": "map-clipped, no re-ID",
                        "raw": "raw count, overlap not removed – overcounts"},
        "det_unplaced": "plus {boxes} boxes on images outside the map (oblique/panorama), not deduplicated",
        "det_none": "no AI detections available (detection not run or nothing found) – report based on imagery only",
        "det_running": "detection still running – results incomplete",
        "fire": "Fire/smoke (AI)",
        "fire_value": "{name} in {images} image(s)",
        "thermal": "Thermal hotspots",
        "thermal_value": "{count} image(s) above {threshold:.0f} °C, max {max:.0f} °C{where}",
        "key_hazards": "Key hazards:",
        "none": "none",
        "unknown": "unknown",
        "disclaimer": "AI-generated from UAV imagery – verify before operational use.",
    },
    "de": {
        "title": "LAGEBILD",
        "generated": "Erstellt {time} UTC mit {model} · {detail} · {analysed} von {total} Bildern ausgewertet",
        "detail_names": {"fast": "schnell", "medium": "mittel", "detailed": "detailliert"},
        "general": "1. ALLGEMEINE LAGE",
        "own": "2. EIGENE LAGE (UAV-ERKUNDUNG)",
        "hazards": "3. GEFAHREN- UND SCHADENSLAGE",
        "open": "4. OFFENE PUNKTE / EINSCHRÄNKUNGEN",
        "location": "Einsatzort",
        "flight_time": "Flugzeit",
        "weather": "Wetter",
        "uav": "UAV",
        "duration": "Flugdauer",
        "height": "Mittl. Flughöhe",
        "area": "Erkundete Fläche",
        "images": "Bilder",
        "detections": "Detektionen (KI)",
        "det_value": "{counts} – geschätzte eindeutige Objekte ({method}) aus {raw} Boxen in überlappenden Bildern",
        "det_methods": {"reid": "Re-ID", "clipped": "kartenbereinigt, ohne Re-ID",
                        "raw": "Rohzählung, Überlappung nicht bereinigt – zu hoch"},
        "det_unplaced": "zzgl. {boxes} Boxen in Bildern außerhalb der Karte (schräg/Panorama), nicht bereinigt",
        "det_none": "keine KI-Detektionen vorhanden (nicht ausgeführt oder nichts gefunden) – Bericht nur aus Bildauswertung",
        "det_running": "Detektion läuft noch – Ergebnisse unvollständig",
        "fire": "Feuer/Rauch (KI)",
        "fire_value": "{name} in {images} Bild(ern)",
        "thermal": "Thermische Hotspots",
        "thermal_value": "{count} Bild(er) über {threshold:.0f} °C, max. {max:.0f} °C{where}",
        "key_hazards": "Wesentliche Gefahren:",
        "none": "keine",
        "unknown": "unbekannt",
        "disclaimer": "KI-generiert aus UAV-Bildern – vor operativer Nutzung prüfen.",
    },
}

SYSTEM_PROMPT = (
    "You support fire brigade and rescue incident command by analysing reconnaissance data "
    "from a UAV (drone) flight. Report only what is actually visible or given in the data, "
    "be concise and factual, and say so when something is uncertain. Focus on what matters "
    "to first responders: hazards, damage, persons at risk, emergency forces and access routes. "
    f"Thermal readings below {HOTSPOT_TEMP_C:.0f} °C are normal for sun-warmed roofs, vehicles and "
    "machinery and are not a hazard on their own."
)

logger = logging.getLogger(__name__)

r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0)


# ---------------------------------------------------------------------------
# Structured model outputs
# ---------------------------------------------------------------------------

class ImageFindings(BaseModel):
    scene: str = Field(description="What the image shows overall: land use, buildings, roads, vegetation. One sentence.")
    hazards: list[str] = Field(description="Visible hazards (fire, smoke, collapse risk, water, spilled substances, power lines...). Empty if none.")
    damage: list[str] = Field(description="Visible damage to buildings, vehicles, infrastructure or terrain. Empty if none.")
    people: str = Field(description="Persons visible, rough count and situation, or 'none visible'.")
    forces_and_vehicles: str = Field(description="Emergency forces/vehicles and other vehicles visible, or 'none visible'.")
    access: str = Field(description="Access routes, blocked roads, obstacles, possible staging areas. Short.")
    relevance: Literal["none", "low", "medium", "high"] = Field(description="Relevance of this image for incident command.")


class MapOverview(BaseModel):
    layout: str = Field(description="Overall layout of the mapped area: type of area, main structures, roads. 1-3 sentences.")
    notable_areas: list[str] = Field(description="Notable areas with their rough position in the map (e.g. 'smoke in the north-east'). Empty if none.")


class AreaSummary(BaseModel):
    observations: str = Field(description="What this part of the flight shows overall, merged across its images, with rough positions. 1-3 sentences.")
    hazards: list[str] = Field(description="Hazards with rough position. Empty if none.")
    damage: list[str] = Field(description="Damage with rough position. Empty if none.")
    people: str = Field(description="Persons seen (merged, avoid double counting overlapping images), or 'none visible'.")
    forces_and_vehicles: str = Field(description="Emergency forces and vehicles seen, or 'none visible'.")
    access: str = Field(description="Access routes, obstacles, staging areas. Short.")


class SituationReport(BaseModel):
    general_situation: str = Field(description="General situation: what kind of area and event, overall picture. 2-5 sentences.")
    own_situation: str = Field(description="Emergency forces, their vehicles, staging areas and usable access routes as seen in the imagery "
                                           "(not the UAV flight itself). 1-3 sentences.")
    hazards_damage: str = Field(description="Hazard and damage situation: hazards, damage extent, persons at risk, with rough positions. 2-6 sentences.")
    key_hazards: list[str] = Field(description="The most important hazards as short bullet points, most critical first. Empty if none.")
    open_points: list[str] = Field(description="Uncertainties, areas not covered, things that need verification on site. Short bullet points.")


# ---------------------------------------------------------------------------
# Celery task + entry point
# ---------------------------------------------------------------------------

@celery_app.task(name="description.situation_report")
def create_situation_report(report_id: int, detail: str = "fast", language: Optional[str] = None):
    language = language if language in LABELS else REPORT_LANGUAGE if REPORT_LANGUAGE in LABELS else "en"
    detail = detail if detail in DETAIL_LEVELS else "fast"
    client = ollama.Client(host=OLLAMA_HOST, timeout=REQUEST_TIMEOUT)
    set_redis_progress(report_id, 1.0)
    try:
        ensure_model(client, report_id)
        set_redis_progress(report_id, 5.0)

        context = gather_context(report_id, detail)
        logger.info(
            f"Situation report {report_id} ({detail}, {language}): {len(context['images'])} of "
            f"{context['candidate_count']} images selected, map={'yes' if context['map_path'] else 'no'}, "
            f"detections={context['detections']['status']}/{context['detections']['method']}"
        )
        set_redis_progress(report_id, 10.0)

        findings = analyse_images(client, context, report_id)  # 10 -> 75

        area_summaries = summarise_areas(client, findings, report_id)  # 75 -> 85, only for many images
        overview = analyse_map(client, context["map_path"]) if context["map_path"] else None
        set_redis_progress(report_id, 88.0)

        report = synthesise_report(client, context, findings, area_summaries, overview, language)
        set_redis_progress(report_id, 95.0)

        text = render_report(context, report, len(findings), language)

        db = next(get_db())
        try:
            report_crud.set_auto_description(db, report_id, text)
        finally:
            db.close()

        set_redis_progress(report_id, 100.0, description=text)
    except Exception as e:
        logger.exception(f"Error creating situation report for report {report_id}: {e}")
        set_redis_progress(report_id, -1.0)
    finally:
        unload_model(client)


def start_description_process(report_id: int, db: Session, detail: str = "fast", language: Optional[str] = None):
    report = report_crud.get_basic_report(db, report_id)
    if not report:
        raise ValueError("Report not found")

    existing_task_id = r.get(f"description:{report_id}:task_id")
    if existing_task_id:
        progress = r.get(f"description:{report_id}:progress")
        status = r.get(f"description:{report_id}:status")
        if status in [b"processing", b"queued"]:
            raise ValueError("Description process already running for this report")
        if progress and float(progress) < 100.0:
            raise ValueError("Description process already running for this report")

    task = create_situation_report.delay(report_id, detail, language)
    r.set(f"description:{report_id}:status", "queued")
    r.set(f"description:{report_id}:progress", 0.0)
    r.set(f"description:{report_id}:task_id", task.id)
    events_service.publish_event(
        r, report_id, events_service.EVENT_DESCRIPTION_STATUS,
        status="queued", progress=0.0,
    )
    return {"status": "started", "task_id": task.id}


def set_redis_progress(report_id: int, progress: float, description: str = ""):
    status = "processing" if 0.0 <= progress < 100.0 else "completed" if progress >= 100.0 else "error"
    if progress < 0.0:
        progress = 100.0

    r.set(f"description:{report_id}:progress", progress)
    r.set(f"description:{report_id}:status", status)

    # The completion event carries the final text so the frontend doesn't need a follow-up fetch.
    events_service.publish_event(
        r, report_id, events_service.EVENT_DESCRIPTION_STATUS,
        status=status, progress=progress,
        data={"description": description} if description else None,
    )


# ---------------------------------------------------------------------------
# Model management
# ---------------------------------------------------------------------------

def ensure_model(client: ollama.Client, report_id: int):
    """
    Pull the model only if it isn't available locally yet (first run on a new machine, ~6 GB).

    The pull is streamed: Ollama then sends progress updates continuously, so the client's
    per-read timeout never fires on long downloads, and the download maps onto progress 1 -> 5 %.
    """
    try:
        client.show(MODEL)
        return
    except ollama.ResponseError as e:
        if e.status_code != 404:
            raise
    logger.info(f"Model {MODEL} not found locally, pulling...")
    layers: dict[str, tuple[int, int]] = {}  # digest -> (completed, total)
    last_reported = 0.0
    for update in client.pull(MODEL, stream=True):
        if update.digest and update.total:
            layers[update.digest] = (update.completed or 0, update.total)
        total = sum(t for _, t in layers.values())
        fraction = sum(c for c, _ in layers.values()) / total if total else 0.0
        if fraction - last_reported >= 0.02:  # throttle Redis/SSE updates
            if int(fraction * 10) > int(last_reported * 10):
                logger.info(f"Pulling {MODEL}: {fraction:.0%} of {total / 1e9:.1f} GB")
            last_reported = fraction
            set_redis_progress(report_id, 1.0 + 4.0 * fraction)
    logger.info(f"Model {MODEL} pulled")


def unload_model(client: ollama.Client):
    """Unload the model right away (keep_alive=0) so the VRAM is free for other workers."""
    try:
        client.generate(model=MODEL, keep_alive=0)
        still_loaded = [m.model for m in client.ps().models if m.model == MODEL]
        if still_loaded:
            logger.warning(f"Model {MODEL} is still loaded after unload request")
        else:
            logger.info(f"Model {MODEL} unloaded")
    except Exception as e:
        logger.error(f"Failed to unload model {MODEL}: {e}")


# ---------------------------------------------------------------------------
# Context gathering (DB -> plain dicts, so the session can be closed early)
# ---------------------------------------------------------------------------

def gather_context(report_id: int, detail: str = "fast") -> dict:
    db = next(get_db())
    try:
        report = report_crud.get_basic_report(db, report_id)
        if not report or not report.mapping_report:
            raise ValueError("Report not found or not a mapping report")
        mr = report.mapping_report
        images = images_crud.get_by_report_full(db, report_id)

        weather = None
        if mr.weather:
            w = max(mr.weather, key=lambda w: w.timestamp or datetime.min)
            weather = {
                "description": w.description, "temperature": w.temperature,
                "wind_speed": w.wind_speed, "wind_dir_deg": w.wind_dir_deg,
                "visibility": w.visibility,
            }

        detections = summarise_detections(images, mr.maps, report_id)

        # Thermal hotspots, mapped onto the RGB counterpart where there is one.
        hotspots = []
        rgb_hot_temp: dict[int, float] = {}
        for img in images:
            td = img.thermal_data
            if not img.thermal or td is None or td.max_temp is None:
                continue
            if td.max_temp >= HOTSPOT_TEMP_C:
                hotspots.append({"max_temp": td.max_temp, "xy": _utm_xy(img.coord)})
            if td.counterpart_id is not None:
                rgb_hot_temp[td.counterpart_id] = max(td.max_temp, rgb_hot_temp.get(td.counterpart_id, -273.0))

        candidates = []
        for img in images:
            if img.thermal or img.panoramic or not img.url or not os.path.exists(img.url):
                continue
            md = img.mapping_data
            det_counts: dict[str, int] = {}
            for det in img.detections:
                det_counts[det.class_name] = det_counts.get(det.class_name, 0) + 1
            candidates.append({
                "id": img.id,
                "path": img.url,
                "created_at": img.created_at,
                "xy": _utm_xy(img.coord),
                "rel_alt": (md.rel_altitude if md and md.rel_altitude is not None
                            else (img.coord or {}).get("rel_alt")),
                "cam_pitch": md.cam_pitch if md else None,
                "detections": det_counts,
                "thermal_max": rgb_hot_temp.get(img.id),
            })

        all_xy = [c["xy"] for c in candidates if c["xy"]] + [h["xy"] for h in hotspots if h["xy"]]
        center = _centroid(all_xy)
        for c in candidates:
            c["position"] = _relative_position(c["xy"], center)
        for h in hotspots:
            h["position"] = _relative_position(h["xy"], center)

        selected = select_images(candidates, detail)
        if not selected:
            raise ValueError("No suitable RGB images found for the situation report")

        return {
            "report_id": report_id,
            "title": report.title,
            "address": mr.address,
            "flight_timestamp": mr.flight_timestamp,
            "flight_duration": mr.flight_duration,
            "flight_height": mr.flight_height,
            "covered_area": mr.covered_area,
            "uav": mr.uav,
            "image_count": mr.image_count or len(images),
            "weather": weather,
            "detail": detail,
            "detections": detections,
            "hotspots": sorted(hotspots, key=lambda h: -h["max_temp"]),
            "candidate_count": len(candidates),
            "images": selected,
            "map_path": _pick_map(mr.maps),
        }
    finally:
        db.close()


def summarise_detections(images, maps, report_id: int) -> dict:
    """
    Detection status and estimated number of distinct objects per class.

    Overlapping images see the same object many times (400 boxes can be ~35 people), so the
    count mirrors the DetectionCard's "reduced" mode (frontend/src/utils/detectionUtils.ts,
    reduceDetections + countReduced): re-ID clusters count once, ungrouped boxes only count
    inside the Voronoi cell their image owns in the mosaic. Without any map there is nothing
    to clip against, so the raw count is used and flagged as an overcount.
    """
    all_dets = [d for img in images for d in img.detections]
    running = r.get(f"detection:{report_id}:status") in (b"queued", b"processing")
    has_ai = any(not d.manually_created for d in all_dets)
    status = "running" if running else "available" if has_ai else "none"

    passing = [d for d in all_dets if (d.score or 0.0) >= DETECTION_SCORE_THRESHOLD]
    fire_images: dict[str, set] = {}
    objects = []
    for d in passing:
        if d.class_name.lower() in FIRE_CLASSES:
            fire_images.setdefault(d.class_name, set()).add(d.image_id)
        else:
            objects.append(d)

    raw_boxes = len(objects)
    elements = [el for m in maps or [] for el in m.map_elements or []]
    # image_id -> Voronoi cell in GPS; like the frontend, later maps overwrite earlier ones
    voronoi = {el.image_id: el.voronoi_gps for el in elements if el.voronoi_gps}

    counts: dict[str, int] = {}
    cluster_class: dict[int, str] = {}  # re-ID cluster -> class of its first member
    unplaced: dict[str, int] = {}       # ungrouped boxes that can't be placed on the map
    if voronoi:
        image_by_id = {img.id: img for img in images}
        first_element: dict[int, object] = {}  # like the frontend: first map element of the image
        for el in elements:
            first_element.setdefault(el.image_id, el)
        for d in objects:
            # Re-ID clusters count once even when they can't be placed on the map
            # (the card's reduced view drops unplaceable ones; the report shouldn't lose them).
            if d.unique_object_id is not None:
                cluster_class.setdefault(d.unique_object_id, d.class_name)
                continue
            gps = (d.coord or {}).get("gps") or _detection_gps(d, image_by_id.get(d.image_id),
                                                                first_element.get(d.image_id))
            if not gps:
                # oblique / panorama images aren't part of the map: can't be deduplicated
                unplaced[d.class_name] = unplaced.get(d.class_name, 0) + 1
                continue
            cell = voronoi.get(d.image_id)
            if cell is None or _point_in_polygon((gps["lat"], gps["lon"]), cell):
                counts[d.class_name] = counts.get(d.class_name, 0) + 1
    else:
        # no map to clip against: raw boxes (re-ID clusters still merged)
        for d in objects:
            if d.unique_object_id is not None:
                cluster_class.setdefault(d.unique_object_id, d.class_name)
            else:
                counts[d.class_name] = counts.get(d.class_name, 0) + 1
    for class_name in cluster_class.values():
        counts[class_name] = counts.get(class_name, 0) + 1

    return {
        "status": status,
        "method": "reid" if cluster_class else "clipped" if voronoi else "raw",
        "counts": dict(sorted(counts.items(), key=lambda kv: -kv[1])),
        "raw_boxes": raw_boxes,
        "unplaced": dict(sorted(unplaced.items(), key=lambda kv: -kv[1])),
        "fire_images": {name: len(ids) for name, ids in fire_images.items()},
    }


def _detection_gps(det, image, element) -> Optional[dict]:
    """
    GPS of the bbox centre, bilinear between the map element's GPS corners.
    Port of computeDetectionGps in frontend/src/utils/coordinateUtils.ts (bbox = [x, y, w, h]).
    """
    try:
        if image is None or not image.coord or element is None:
            return None
        corners = element.corners["gps"]
        rel_x = (float(det.bbox[0]) + float(det.bbox[2]) / 2) / image.width
        rel_y = (float(det.bbox[1]) + float(det.bbox[3]) / 2) / image.height
        top_right, bottom_right, bottom_left, top_left = corners[1], corners[2], corners[3], corners[0]
        top = [top_left[i] * (1 - rel_x) + top_right[i] * rel_x for i in (0, 1)]
        bottom = [bottom_left[i] * (1 - rel_x) + bottom_right[i] * rel_x for i in (0, 1)]
        return {"lat": top[0] * (1 - rel_y) + bottom[0] * rel_y, "lon": top[1] * (1 - rel_y) + bottom[1] * rel_y}
    except (KeyError, IndexError, TypeError, ValueError, ZeroDivisionError):
        return None


def _point_in_polygon(point: tuple[float, float], polygon: list) -> bool:
    """Ray casting, same as isPointInPolygon in frontend/src/utils/coordinateUtils.ts ([lat, lon] order)."""
    px, py = point
    inside = False
    j = len(polygon) - 1
    for i in range(len(polygon)):
        xi, yi = polygon[i]
        xj, yj = polygon[j]
        if (yi > py) != (yj > py) and px < (xj - xi) * (py - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


def _is_critical(c: dict) -> bool:
    """Thermal hotspot or fire/smoke detection: never skipped by image sampling."""
    hot = c["thermal_max"] is not None and c["thermal_max"] >= HOTSPOT_TEMP_C
    return hot or any(name.lower() in FIRE_CLASSES for name in c["detections"])


def select_images(candidates: list[dict], detail: str = "fast") -> list[dict]:
    """
    - detailed: every image
    - medium:   every second image (in flight order), plus any skipped hotspot / fire image
    - fast:     at most FAST_MAX_IMAGES, see _select_fast
    """
    ordered = sorted(candidates, key=_time_key)
    if detail == "detailed":
        return ordered
    if detail == "medium":
        return sorted(ordered[::2] + [c for c in ordered[1::2] if _is_critical(c)], key=_time_key)
    return _select_fast(candidates, FAST_MAX_IMAGES)


def _select_fast(candidates: list[dict], budget: int) -> list[dict]:
    """
    Pick at most `budget` images: first the ones with thermal hotspots or detections
    (up to half the budget), then fill up with farthest-point sampling for spatial coverage
    (or evenly spaced in time when there are no coordinates).
    """
    if len(candidates) <= budget:
        return sorted(candidates, key=_time_key)

    def priority(c):
        temp = c["thermal_max"] if c["thermal_max"] is not None else -273.0
        return (temp >= HOTSPOT_TEMP_C, sum(c["detections"].values()), temp)

    flagged = [c for c in candidates if (c["thermal_max"] or -273.0) >= HOTSPOT_TEMP_C or c["detections"]]
    flagged.sort(key=priority, reverse=True)
    selected = flagged[: budget // 2]
    chosen_ids = {c["id"] for c in selected}
    rest = [c for c in candidates if c["id"] not in chosen_ids]

    with_xy = [c for c in rest if c["xy"]]
    if len(with_xy) >= budget - len(selected):
        anchors = [c["xy"] for c in selected if c["xy"]]
        if not anchors:
            center = _centroid([c["xy"] for c in with_xy])
            first = min(with_xy, key=lambda c: _dist(c["xy"], center))
            selected.append(first)
            anchors.append(first["xy"])
            with_xy.remove(first)
        # min distance of every remaining image to the already selected ones
        min_d = [min(_dist(c["xy"], a) for a in anchors) for c in with_xy]
        while len(selected) < budget and with_xy:
            i = max(range(len(with_xy)), key=min_d.__getitem__)
            pick = with_xy.pop(i)
            min_d.pop(i)
            selected.append(pick)
            min_d = [min(d, _dist(c["xy"], pick["xy"])) for d, c in zip(min_d, with_xy)]
    else:
        rest.sort(key=_time_key)
        n = budget - len(selected)
        step = len(rest) / n
        selected += [rest[int(i * step)] for i in range(n)]

    return sorted(selected, key=_time_key)


def _pick_map(maps) -> Optional[str]:
    """Prefer an RGB map, then ODM > advanced > fast, then newest."""
    existing = [m for m in maps or [] if m.url and os.path.exists(m.url)]
    if not existing:
        return None

    def rank(m):
        name = (m.name or "").lower()
        is_rgb = "_ir" not in name and "thermal" not in name
        kind = 2 if m.odm or name.startswith("odm") else 1 if name.startswith("advanced") else 0
        return (is_rgb, kind, m.created_at or datetime.min, m.id)

    return max(existing, key=rank).url


# ---------------------------------------------------------------------------
# Model calls
# ---------------------------------------------------------------------------

def analyse_images(client: ollama.Client, context: dict, report_id: int) -> list[dict]:
    images = context["images"]
    total = len(images)
    results: list[Optional[dict]] = [None] * total
    done = 0

    with ThreadPoolExecutor(max_workers=PARALLEL_REQUESTS) as executor:
        futures = {
            executor.submit(_analyse_image, client, img, i + 1, total, context["address"]): i
            for i, img in enumerate(images)
        }
        for future in as_completed(futures):
            i = futures[future]
            try:
                results[i] = {"index": i + 1, "image": images[i], "findings": future.result()}
            except Exception as e:
                logger.error(f"Image analysis failed for image {images[i]['id']}: {e}")
            done += 1
            set_redis_progress(report_id, 10.0 + done / total * 65.0)

    findings = [res for res in results if res is not None]
    if not findings:
        raise RuntimeError("Image analysis failed for all images")
    return findings


def _analyse_image(client: ollama.Client, img: dict, index: int, total: int, address: Optional[str]) -> ImageFindings:
    prompt = (
        f"Image {index} of {total} from a UAV reconnaissance flight"
        f"{f' at {address}' if address else ''}.\n"
        f"{_image_context_line(img)}\n"
        "Analyse the image and fill in the JSON fields. Keep each field brief. "
        "Use empty lists or 'none visible' when there is nothing relevant."
    )
    return _structured_chat(client, ImageFindings, prompt, _encode_image(img["path"], IMAGE_MAX_SIDE))


def analyse_map(client: ollama.Client, map_path: str) -> Optional[MapOverview]:
    try:
        prompt = (
            "This is an orthophoto map stitched from all images of the UAV flight, north is up. "
            "Black or transparent areas are outside the mapped area. "
            "Describe the overall layout and notable areas with their position in the map."
        )
        return _structured_chat(client, MapOverview, prompt, _encode_image(map_path, MAP_MAX_SIDE, is_map=True))
    except Exception as e:
        logger.error(f"Map overview failed for {map_path}: {e}")
        return None


def summarise_areas(client: ollama.Client, findings: list[dict], report_id: int) -> Optional[list[AreaSummary]]:
    """
    Map step for large runs: with more than CHUNK_SIZE findings the per-image lines don't fit into
    NUM_CTX, so consecutive chunks of the flight (roughly spatially coherent along the flight path)
    are summarised first. Returns None when the findings are few enough to synthesise directly.
    """
    if len(findings) <= CHUNK_SIZE:
        return None
    chunks = [findings[i:i + CHUNK_SIZE] for i in range(0, len(findings), CHUNK_SIZE)]
    results: list[Optional[AreaSummary]] = [None] * len(chunks)
    done = 0

    def summarise(k: int, chunk: list[dict]) -> AreaSummary:
        prompt = (
            f"Findings from part {k + 1} of {len(chunks)} of a UAV reconnaissance flight "
            f"({_fmt_time(chunk[0]['image']['created_at'])} to {_fmt_time(chunk[-1]['image']['created_at'])}). "
            "The images overlap, so the same persons, vehicles and objects appear in several of them: merge "
            "them instead of adding them up. Keep positions relative to the flight centre.\n\n"
            + _findings_block(chunk)
        )
        return _structured_chat(client, AreaSummary, prompt)

    with ThreadPoolExecutor(max_workers=PARALLEL_REQUESTS) as executor:
        futures = {executor.submit(summarise, k, chunk): k for k, chunk in enumerate(chunks)}
        for future in as_completed(futures):
            k = futures[future]
            try:
                results[k] = future.result()
            except Exception as e:
                logger.error(f"Area summary {k + 1}/{len(chunks)} failed: {e}")
            done += 1
            set_redis_progress(report_id, 75.0 + done / len(chunks) * 10.0)

    summaries = [s for s in results if s is not None]
    if not summaries:
        raise RuntimeError("Area summaries failed for all chunks")
    return summaries


def synthesise_report(client: ollama.Client, context: dict, findings: list[dict],
                      area_summaries: Optional[list[AreaSummary]], overview: Optional[MapOverview],
                      language: str) -> SituationReport:
    lines = ["MISSION DATA:", _mission_facts(context), ""]
    if area_summaries:
        lines.append("AREA SUMMARIES (the flight split into consecutive parts, positions relative to the flight centre):")
        for k, a in enumerate(area_summaries):
            parts = [a.observations]
            if a.hazards:
                parts.append("hazards: " + "; ".join(a.hazards))
            if a.damage:
                parts.append("damage: " + "; ".join(a.damage))
            parts += [f"people: {a.people}", f"forces/vehicles: {a.forces_and_vehicles}", f"access: {a.access}"]
            lines.append(f"- Part {k + 1}: " + " | ".join(parts))
    else:
        lines += ["PER-IMAGE FINDINGS (positions relative to the flight centre):", _findings_block(findings)]
    if overview:
        lines += ["", "ORTHOPHOTO OVERVIEW:", overview.layout]
        lines += [f"- {a}" for a in overview.notable_areas]

    prompt = (
        "\n".join(lines)
        + "\n\nWrite a situation report for incident command from this data, structured like a German "
        "'Lagebild' (general situation, own situation, hazard and damage situation). "
        "Merge observations from overlapping images into one consistent picture instead of listing images "
        "or parts, never mention image or part numbers, and refer to places by their position relative to "
        "the flight centre. If no hazards are visible, say so clearly. "
        + _detection_rules(context["detections"])
        + " The mission data (location, time, weather, flight data, detection counts, thermal summary) is "
        "already printed above each section, so do not restate it; only interpret it where it matters. "
        f"Write all text in {LANGUAGE_NAMES.get(language, 'English')}."
    )
    return _structured_chat(client, SituationReport, prompt, options=SYNTHESIS_OPTIONS)


def _detection_rules(det: dict) -> str:
    """Prompt rules matching how far the object detection results can be trusted."""
    if det["status"] == "none":
        return ("No object detection results are available: detection was not run or found nothing. Do not "
                "draw conclusions from missing detections, and add an open point that running the object "
                "detection would give person and vehicle counts.")
    rules = ""
    if det["status"] == "running":
        rules += ("Object detection is still running, so its results are incomplete; add an open point to "
                  "regenerate the report once it has finished. ")
    if det["method"] == "raw":
        rules += ("The detection counts are raw boxes summed over overlapping images and overcount heavily; "
                  "never present them as the number of persons or vehicles. ")
    else:
        rules += ("The detection counts are estimates of distinct objects after removing duplicates from "
                  "overlapping images; present them as approximate. ")
    if det.get("unplaced"):
        rules += ("Boxes on images outside the map (oblique or panorama views) could not be deduplicated and "
                  "likely show objects already counted; do not add them to the estimates. ")
    rules += ("Where the object detector and the image findings disagree (e.g. detected persons not described), "
              "do not dismiss either: flag it as needing verification on site, since small objects are easy "
              "to miss from the air.")
    return rules


def _findings_block(findings: list[dict]) -> str:
    """One line per relevant image; images without relevant findings are folded into a count."""
    lines, irrelevant = [], 0
    for f in findings:
        img, fi = f["image"], f["findings"]
        if fi.relevance == "none" and not img["detections"] and not _is_critical(img):
            irrelevant += 1
            continue
        parts = [f"scene: {fi.scene}"]
        if fi.hazards:
            parts.append("hazards: " + "; ".join(fi.hazards))
        if fi.damage:
            parts.append("damage: " + "; ".join(fi.damage))
        parts += [f"people: {fi.people}", f"forces/vehicles: {fi.forces_and_vehicles}", f"access: {fi.access}"]
        if img["detections"]:
            parts.append("detector boxes in this image: " + ", ".join(f"{n} {name}" for name, n in img["detections"].items()))
        if img["thermal_max"] is not None:
            parts.append(f"thermal max {img['thermal_max']:.0f} °C")
        lines.append(f"- {img['position']} ({_fmt_time(img['created_at'])}, relevance {fi.relevance}): "
                     + " | ".join(parts))
    if irrelevant:
        lines.append(f"- {irrelevant} further image(s) without relevant findings")
    return "\n".join(lines)


def _structured_chat(client: ollama.Client, schema: type[BaseModel], prompt: str,
                     image_b64: Optional[str] = None, options: dict = MODEL_OPTIONS):
    """One chat call constrained to `schema`, retried when the JSON comes back invalid or truncated."""
    # `format` only constrains the syntax; the field descriptions have to be in the prompt to be seen.
    field_guide = "\n".join(f"- {name}: {field.description}" for name, field in schema.model_fields.items())
    user_msg = {"role": "user", "content": f"{prompt}\n\nAnswer as JSON with these fields:\n{field_guide}"}
    if image_b64:
        user_msg["images"] = [image_b64]
    for attempt in range(JSON_RETRIES + 1):
        response = client.chat(
            model=MODEL,
            messages=[{"role": "system", "content": SYSTEM_PROMPT}, user_msg],
            format=schema.model_json_schema(),
            options=options,
            keep_alive=KEEP_ALIVE,
        )
        try:
            return schema.model_validate_json(response.message.content)
        except ValidationError as e:
            if attempt == JSON_RETRIES:
                raise
            logger.warning(f"Invalid {schema.__name__} JSON (done_reason={response.done_reason}), retrying: {e}")


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def render_report(context: dict, report: SituationReport, analysed: int, language: str) -> str:
    L = LABELS[language]
    unknown = L["unknown"]
    weather = context["weather"]

    def fact(label, value):
        return f"{L[label]}: {value if value not in (None, '') else unknown}"

    out = [
        f"{L['title']} – {context['address'] or context['title'] or unknown}",
        L["generated"].format(time=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"), model=MODEL,
                              detail=L["detail_names"][context["detail"]],
                              analysed=analysed, total=context["candidate_count"]),
        "",
        L["general"],
        fact("location", context["address"]),
        fact("flight_time", _fmt_time(context["flight_timestamp"])),
        fact("weather", _fmt_weather(weather)),
        report.general_situation.strip(),
        "",
        L["own"],
        fact("uav", context["uav"]),
        fact("duration", _fmt_duration(context["flight_duration"])),
        fact("height", f"{context['flight_height']:.0f} m" if context["flight_height"] else None),
        fact("area", _fmt_area(context["covered_area"])),
        fact("images", context["image_count"]),
        report.own_situation.strip(),
        "",
        L["hazards"],
        fact("detections", _fmt_detections(context["detections"], L)),
    ]
    if context["detections"]["fire_images"]:
        out.append(fact("fire", _fmt_fire(context["detections"], L)))
    out += [
        fact("thermal", _fmt_hotspots(context["hotspots"], L) or L["none"]),
        report.hazards_damage.strip(),
    ]
    if report.key_hazards:
        out += [L["key_hazards"]] + [f"- {h.strip()}" for h in report.key_hazards]
    out += ["", L["open"]]
    out += [f"- {p.strip()}" for p in report.open_points] or [f"- {L['none']}"]
    out += ["", L["disclaimer"]]
    return "\n".join(out)


def _mission_facts(context: dict) -> str:
    en = LABELS["en"]
    det = context["detections"]
    hot = _fmt_hotspots(context["hotspots"], en) or "none"
    lines = [
        f"Location: {context['address'] or 'unknown'}",
        f"Time of flight: {_fmt_time(context['flight_timestamp'])}",
        f"Weather: {_fmt_weather(context['weather'])}",
        f"AI object detection over the whole flight (may contain errors): {_fmt_detections(det, en)}",
    ]
    if det["fire_images"]:
        lines.append(f"AI fire/smoke detection: {_fmt_fire(det, en)}")
    lines.append(f"Thermal hotspots: {hot}")
    return "\n".join(lines)


def _fmt_detections(det: dict, L: dict) -> str:
    if det["status"] == "none":
        return L["det_none"]
    if not det["counts"]:
        return L["det_running"] if det["status"] == "running" else L["none"]
    counts = ", ".join(f"~{n} {name}" for name, n in det["counts"].items()) or L["none"]
    text = L["det_value"].format(counts=counts, method=L["det_methods"][det["method"]], raw=det["raw_boxes"])
    if det["unplaced"]:
        boxes = ", ".join(f"{n} {name}" for name, n in det["unplaced"].items())
        text += "; " + L["det_unplaced"].format(boxes=boxes)
    return f"{text}; {L['det_running']}" if det["status"] == "running" else text


def _fmt_fire(det: dict, L: dict) -> str:
    return ", ".join(L["fire_value"].format(name=name, images=n) for name, n in det["fire_images"].items())


def _image_context_line(img: dict) -> str:
    parts = [f"Taken {_fmt_time(img['created_at'])}, {img['position']}"]
    if img["rel_alt"] is not None:
        parts.append(f"{img['rel_alt']:.0f} m above ground")
    if img["cam_pitch"] is not None:
        parts.append("camera pointing straight down" if img["cam_pitch"] <= -80 else
                     f"oblique view (camera pitch {img['cam_pitch']:.0f}°)")
    line = ", ".join(parts) + "."
    if img["detections"]:
        dets = ", ".join(f"{n} {name}" for name, n in img["detections"].items())
        line += f" An object detector reported (may contain errors): {dets}."
    if img["thermal_max"] is not None:
        line += f" The thermal camera measured up to {img['thermal_max']:.0f} °C at this spot."
    return line


def _fmt_time(value) -> str:
    return value.strftime("%Y-%m-%d %H:%M") if isinstance(value, datetime) else "unknown"


def _fmt_duration(seconds) -> Optional[str]:
    if not seconds:
        return None
    minutes = int(round(seconds / 60))
    return f"{minutes // 60} h {minutes % 60:02d} min" if minutes >= 60 else f"{minutes} min"


def _fmt_area(m2) -> Optional[str]:
    if not m2:
        return None
    return f"{m2 / 10000:.1f} ha" if m2 >= 10000 else f"{m2:.0f} m²"


def _fmt_weather(w: Optional[dict]) -> Optional[str]:
    if not w:
        return None
    parts = [w["description"]] if w.get("description") else []
    if w.get("temperature") is not None:
        parts.append(f"{w['temperature']:.0f} °C")
    if w.get("wind_speed") is not None:
        wind = f"wind {w['wind_speed']:.0f} m/s"
        if w.get("wind_dir_deg") is not None:
            wind += f" from {_compass(w['wind_dir_deg'])}"
        parts.append(wind)
    if w.get("visibility") is not None:
        parts.append(f"visibility {w['visibility'] / 1000:.0f} km")
    return ", ".join(parts) or None


def _fmt_hotspots(hotspots: list[dict], L: dict) -> Optional[str]:
    if not hotspots:
        return None
    hottest = hotspots[0]
    where = f" ({hottest['position']})" if hottest.get("xy") else ""
    return L["thermal_value"].format(count=len(hotspots), threshold=HOTSPOT_TEMP_C, max=hottest["max_temp"], where=where)


# ---------------------------------------------------------------------------
# Geometry + image helpers
# ---------------------------------------------------------------------------

def _utm_xy(coord) -> Optional[tuple[float, float]]:
    utm = (coord or {}).get("utm") or {}
    if utm.get("easting") is None or utm.get("northing") is None:
        return None
    return float(utm["easting"]), float(utm["northing"])


def _centroid(points: list[tuple[float, float]]) -> Optional[tuple[float, float]]:
    if not points:
        return None
    return sum(p[0] for p in points) / len(points), sum(p[1] for p in points) / len(points)


def _dist(a, b) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _compass(deg: float) -> str:
    return ["N", "NE", "E", "SE", "S", "SW", "W", "NW"][int(((deg % 360) + 22.5) // 45) % 8]


def _relative_position(xy, center) -> str:
    if not xy or not center:
        return "position unknown"
    d = _dist(xy, center)
    if d < 15:
        return "near the flight centre"
    bearing = math.degrees(math.atan2(xy[0] - center[0], xy[1] - center[1]))  # 0° = north
    return f"~{d:.0f} m {_compass(bearing)} of the flight centre"


def _time_key(c: dict):
    return c["created_at"] or datetime.min


def _encode_image(path: str, max_side: int, is_map: bool = False) -> str:
    previous_limit = Image.MAX_IMAGE_PIXELS
    if is_map:
        Image.MAX_IMAGE_PIXELS = None  # orthophotos can legitimately exceed PIL's decompression-bomb limit
    try:
        with Image.open(path) as image:
            image.draft("RGB", (max_side, max_side))  # fast JPEG downscaling while decoding
            image = ImageOps.exif_transpose(image)
            image.thumbnail((max_side, max_side))
            buffered = BytesIO()
            image.convert("RGB").save(buffered, format="JPEG", quality=90)
    finally:
        Image.MAX_IMAGE_PIXELS = previous_limit
    return base64.b64encode(buffered.getvalue()).decode("utf-8")
