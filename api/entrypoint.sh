#!/bin/bash
set -e

# Wait for Postgres to be available
echo "Waiting for Postgres..."
while ! nc -z db 5432; do
  echo "Still waiting for Postgres..."
  sleep 0.5
done
echo "Postgres is available!"

# Run Alembic migrations
echo "Running Alembic migrations..."
alembic upgrade head

# Start the FastAPI application
echo "Starting FastAPI server..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
