"""Report event bus: Redis pub/sub publishing + state readers for SSE snapshots.

Contract (shared with the worker codebases — see api/SSE_MIGRATION_PLAN.md):
  channel  argus:events:report:{report_id}
  payload  {"report_id", "type", "status", "progress", "message", "data", "ts"}

Publishing is strictly additive to the existing Redis SET keys — the keys stay
the source of truth for snapshots, reconnects and the polling fallback. A
publish with no subscribers is silently dropped, which is fine.
"""

import json
import logging
import os
import time

import redis
import redis.asyncio as aioredis

from app.config import config

logger = logging.getLogger(__name__)

REPORT_CHANNEL = "argus:events:report:{report_id}"

# Event types carried in the SSE "event:" field
EVENT_SNAPSHOT = "snapshot"
EVENT_REPORT_STATUS = "report_status"
EVENT_COLMAP_STATUS = "colmap_status"
EVENT_DETECTION_STATUS = "detection_status"
EVENT_DESCRIPTION_STATUS = "description_status"
EVENT_RECONSTRUCTION_STATUS = "reconstruction_status"
EVENT_MAP_CREATED = "map_created"
EVENT_DETECTIONS_ADDED = "detections_added"

_sync_redis: redis.Redis | None = None
_async_redis: aioredis.Redis | None = None


def get_sync_redis() -> redis.Redis:
    global _sync_redis
    if _sync_redis is None:
        _sync_redis = redis.Redis(host=config.REDIS_HOST, port=config.REDIS_PORT, db=0)
    return _sync_redis


def get_async_redis() -> aioredis.Redis:
    """Async client for the SSE endpoint only — everything else stays sync."""
    global _async_redis
    if _async_redis is None:
        _async_redis = aioredis.Redis(
            host=config.REDIS_HOST, port=config.REDIS_PORT, db=0, decode_responses=True
        )
    return _async_redis


def publish_event(
    r: redis.Redis,
    report_id: int,
    event_type: str,
    *,
    status: str | None = None,
    progress: float | None = None,
    message: str | None = None,
    data: dict | None = None,
) -> None:
    """Fire-and-forget publish; must never break the caller (worker/task/router)."""
    payload = {
        "report_id": report_id,
        "type": event_type,
        "status": status,
        "progress": progress,
        "message": message,
        "data": data or {},
        "ts": time.time(),
    }
    try:
        r.publish(REPORT_CHANNEL.format(report_id=report_id), json.dumps(payload))
    except Exception:
        logger.warning(f"Failed to publish {event_type} event for report {report_id}", exc_info=True)


# ── Domain state readers (pure, shared by polling routers + SSE snapshot) ─────
# The sync clients in the routers return bytes (decode_responses=False), so all
# readers decode defensively.

def _decode(value) -> str | None:
    if value is None:
        return None
    return value.decode() if isinstance(value, bytes) else str(value)


def read_colmap_state(r: redis.Redis, report_id: int) -> dict:
    status = _decode(r.get(f"colmap:{report_id}:status"))
    progress = _decode(r.get(f"colmap:{report_id}:progress"))
    message = _decode(r.get(f"colmap:{report_id}:message"))
    reconstruction = os.path.join(
        str(config.UPLOAD_DIR), str(report_id), "colmap", "reconstruction.json"
    )
    return {
        "report_id": report_id,
        "status": status or "none",
        "progress": int(float(progress)) if progress else 0,
        "message": message or "",
        "has_reconstruction": os.path.isfile(reconstruction),
    }


def read_detection_state(r: redis.Redis, report_id: int) -> dict | None:
    """Returns None when no detection run exists for this report."""
    status = _decode(r.get(f"detection:{report_id}:status"))
    progress = _decode(r.get(f"detection:{report_id}:progress"))
    message = _decode(r.get(f"detection:{report_id}:message"))
    if not status and not progress:
        return None
    return {
        "report_id": report_id,
        "status": status or "unknown",
        "progress": int(float(progress)) if progress else 0,
        "message": message or "unknown",
    }


def read_description_state(r: redis.Redis, report_id: int) -> dict:
    """Redis-only view (no DB text, no Celery liveness probe — watchdog owns that)."""
    status = _decode(r.get(f"description:{report_id}:status"))
    progress = _decode(r.get(f"description:{report_id}:progress"))
    return {
        "report_id": report_id,
        "status": status or "no_description",
        "progress": float(progress) if progress else 0.0,
        "description": "",
    }


def read_reconstruction_state(r: redis.Redis, report_id: int) -> dict | None:
    """Returns None when no reconstruction run exists for this report."""
    status = _decode(r.get(f"reconstruction:{report_id}:status"))
    progress = _decode(r.get(f"reconstruction:{report_id}:progress"))
    message = _decode(r.get(f"reconstruction:{report_id}:message"))
    if not status and not progress:
        return None
    return {
        "report_id": report_id,
        "status": status or "unknown",
        "progress": int(float(progress)) if progress else 0,
        "message": message or "",
    }


def build_snapshot(report_id: int) -> dict:
    """Full current state of all domains, sent as the first SSE event on every
    (re)connect. Built from the same DB/Redis sources the polling endpoints read.

    Runs sync (DB session + sync Redis) — call via run_in_threadpool from async code.
    """
    # Imported here to keep module import light for the worker processes that
    # only need publish_event.
    import app.crud.report as report_crud
    from app.database import get_db

    r = get_sync_redis()
    db = next(get_db())
    try:
        report = report_crud.read_process_status(db, report_id, r)
        report_state = {
            "report_id": report_id,
            "status": report.status if hasattr(report, "status") else report["status"],
            "progress": report.progress if hasattr(report, "progress") else report["progress"],
        }

        description_state = read_description_state(r, report_id)
        if description_state["status"] in ("completed", "no_description"):
            db_report = report_crud.get_basic_report(db, report_id)
            if db_report is not None and db_report.auto_description:
                description_state["status"] = "completed"
                description_state["progress"] = 100.0
                description_state["description"] = db_report.auto_description

        map_ids = [m.id for m in report_crud.get_mapping_report_maps_slim(db, report_id)]
    finally:
        db.close()

    return {
        "report_id": report_id,
        "type": EVENT_SNAPSHOT,
        "report": report_state,
        "colmap": read_colmap_state(r, report_id),
        "detection": read_detection_state(r, report_id),
        "description": description_state,
        "reconstruction": read_reconstruction_state(r, report_id),
        "map_ids": map_ids,
        "ts": time.time(),
    }
