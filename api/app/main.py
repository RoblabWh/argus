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
    allow_credentials=False,
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