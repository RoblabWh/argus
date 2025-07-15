from fastapi import FastAPI
from . import models, schemas
from .database import SessionLocal, engine
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import inspect
from app.services.on_startup import cleanup_lost_tasks
import os
import redis

from app.routers import (
    groups,
    reports,
    images,
    # weather,
    # detections,
    # processing,
)

models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Argus API",
    description="API for managing reports.",
    version="1.0.0",
)

# Optional CORS setup (adjust origins as needed)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Change to specific domains in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


current_dir = os.path.dirname(os.path.abspath(__file__))
static_dir = os.path.join(current_dir, "../reports_data")
app.mount("/reports_data", StaticFiles(directory=static_dir), name="static")

# Routers will be defined here
app.include_router(groups.router)
app.include_router(reports.router)
app.include_router(images.router)

cleanup_lost_tasks()  # Cleanup lost tasks on startup


@app.get("/")
async def root():
    return {"message": "Welcome to the Report API!", "docs": "/docs"}

@app.get("/db")
async def get_db_info():
    """Returns basic information about the database."""
    from app.database import print_db_info
    print_db_info()
    return {"message": "Database information printed to console."}

inspector = inspect(engine)

for table_name in inspector.get_table_names():
    print(f"Table: {table_name}", flush=True)
    for column in inspector.get_columns(table_name):
        print(f"  Column: {column['name']} - {column['type']} - Nullable: {column['nullable']} default: {column.get('default')} - Server Default: {column.get('server_default')}", flush=True)