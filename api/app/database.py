from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.orm import Session
from fastapi import Depends
import os

from app.config import config
DATABASE_URL = config.DATABASE_URL

engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()



def print_db_info():
    """Prints information about the database tables and their columns."""
    from app import models  # Ensure models are imported to register them with Base
    Base.metadata.tables.keys()  # list of table names

    for table in Base.metadata.sorted_tables:
        print(f"Table: {table.name}")
        for column in table.columns:
            print(f"  {column.name} ({column.type}) - nullable: {column.nullable}, default: {column.default}")