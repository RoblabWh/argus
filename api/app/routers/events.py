"""SSE stream of live report events (see api/SSE_MIGRATION_PLAN.md).

One stream per report multiplexes all processing domains as typed events.
Lifecycle: subscribe to the report's pub/sub channel FIRST (closes the race
window — duplicate state events after the snapshot are idempotent), then send
a full-state ``snapshot`` event, then relay published events until the client
disconnects. Reconnects simply get a fresh snapshot; there is no Last-Event-ID
replay because pub/sub keeps no history.
"""

import json
import logging

from fastapi import APIRouter
from fastapi.concurrency import run_in_threadpool
from sse_starlette.sse import EventSourceResponse, ServerSentEvent

from app.services import events as events_service

router = APIRouter(prefix="/reports", tags=["Events"])

logger = logging.getLogger(__name__)


@router.get("/{report_id}/events")
async def report_events(report_id: int):
    """Server-Sent Events stream for one report.

    Async all the way down: pub/sub uses redis.asyncio (a blocking listen()
    per viewer would pin a threadpool thread each); the snapshot's DB read is
    sync SQLAlchemy and therefore runs via run_in_threadpool.
    """
    channel = events_service.REPORT_CHANNEL.format(report_id=report_id)

    async def event_stream():
        pubsub = events_service.get_async_redis().pubsub()
        await pubsub.subscribe(channel)
        try:
            snapshot = await run_in_threadpool(events_service.build_snapshot, report_id)
            yield ServerSentEvent(
                event=events_service.EVENT_SNAPSHOT,
                data=json.dumps(snapshot),
                id=str(int(snapshot["ts"] * 1000)),
            )

            async for message in pubsub.listen():
                if message.get("type") != "message":
                    continue  # subscribe confirmations etc.
                raw = message["data"]
                try:
                    payload = json.loads(raw)
                    event_type = payload["type"]
                    event_id = str(int(float(payload.get("ts", 0)) * 1000))
                except (ValueError, KeyError, TypeError):
                    logger.warning(f"Dropping malformed event on {channel}: {raw!r}")
                    continue
                yield ServerSentEvent(event=event_type, data=raw, id=event_id)
        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.aclose()

    # ping=15 keeps idle streams alive and lets dead connections be detected,
    # so the finally-cleanup above actually runs for silently-gone clients.
    return EventSourceResponse(event_stream(), ping=15)
