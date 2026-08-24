import logging
import os

# Configure the root logger once here so all app module loggers (which propagate
# to root) respect the LOG_LEVEL env variable. Done before app imports so every
# logger created during module load already inherits the correct level.
logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "WARNING").upper(), logging.WARNING),
    format="[%(levelname)s] %(asctime)s %(name)s - %(message)s",
)

import asyncio
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI
from . import models, schemas
from .database import SessionLocal, engine
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import inspect
from app.services.on_startup import cleanup_lost_tasks
from app.services.status_watchdog import watchdog_loop
import os
import redis

from app.routers import (
    groups,
    reports,
    images,
    odm,
    detection,
    settings,
    transfer,
    reconstruction,
    export,
    events,
)

models.Base.metadata.create_all(bind=engine)


@asynccontextmanager
async def lifespan(app: FastAPI):
    cleanup_lost_tasks()  # Cleanup lost tasks on startup
    watchdog_task = asyncio.create_task(watchdog_loop())
    yield
    watchdog_task.cancel()
    with suppress(asyncio.CancelledError):
        await watchdog_task


app = FastAPI(
    title="Argus API",
    description="API for managing reports.",
    version="1.0.0",
    lifespan=lifespan,
)

# Optional CORS setup (adjust origins as needed)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Change to specific domains in production
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


current_dir = os.path.dirname(os.path.abspath(__file__))
static_dir = os.path.join(current_dir, "../reports_data")


class CORSStaticFiles(StaticFiles):
    """StaticFiles that always emits CORS headers.

    CORSMiddleware only adds `Access-Control-Allow-Origin` when the request
    carries an `Origin` header. Plain `<img src>` loads send none, so their
    response gets cached without it; a later CORS `fetch` of the same URL
    (photo-sphere-viewer's TextureLoader) reuses that cache entry and is
    blocked. Emitting the header unconditionally keeps a single cache entry
    valid for both kinds of consumer.
    """

    async def get_response(self, path: str, scope):
        response = await super().get_response(path, scope)
        response.headers.setdefault("Access-Control-Allow-Origin", "*")
        response.headers.setdefault("Vary", "Origin")
        response.headers.setdefault("Cache-Control", "public, max-age=3600")
        return response


app.mount("/reports_data", CORSStaticFiles(directory=static_dir), name="static")

# Routers will be defined here
app.include_router(groups.router)
app.include_router(reports.router)
app.include_router(images.router)
app.include_router(odm.router)
app.include_router(detection.router)
app.include_router(settings.router)
app.include_router(transfer.router)
app.include_router(reconstruction.router)
app.include_router(export.router)
app.include_router(events.router)


inspector = inspect(engine)

for table in inspector.get_table_names():
    print(f"Table: {table}")
    #print one line for each table with its columns and types
    columns = inspector.get_columns(table)
    for column in columns:
        print(f"  Column: {column['name']} - Type: {column['type']}")   

        
@app.get("/")
async def root():
    return {"message": "Welcome to the Report API!", "docs": "/docs"}

@app.get("/db")
async def get_db_info():
    """Returns basic information about the database."""
    from app.database import print_db_info
    print_db_info()
    return {"message": "Database information printed to console."}



    # for idx in inspector.get_indexes(table):
    #     print(f"  Index: {idx['name']} on columns {idx['column_names']}")
    # for column in inspector.get_columns(table):
    #     print(f"  Column: {column['name']} — Indexed?" +
    #           (" Yes" if any(column['name'] in idx['column_names'] for idx in inspector.get_indexes(table)) else " No"))