from fastapi import FastAPI
from . import models, schemas
from .database import SessionLocal, engine
from fastapi.middleware.cors import CORSMiddleware

from app.routers import (
    groups,
    reports,
    # images,
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

# Routers will be defined here
app.include_router(groups.router)
app.include_router(reports.router)

@app.get("/")
async def root():
    return {"message": "Welcome to the Report API!", "docs": "/docs"}

@app.get("/db")
async def get_db_info():
    """Returns basic information about the database."""
    from app.database import print_db_info
    print_db_info()
    return {"message": "Database information printed to console."}