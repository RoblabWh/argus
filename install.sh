#!/bin/bash
set -e

echo "Building and starting containers..."
docker-compose up -d --build

echo "Waiting for database to be ready..."
until docker exec argusII_project_db pg_isready -U user; do
  sleep 5
done

# Only create initial migration if no versions exist
if [ ! "$(ls -A api/alembic/versions)" ]; then
  echo "Creating initial Alembic migration..."
  docker-compose run --rm api alembic -c /api/alembic.ini revision --autogenerate -m "initial"
fi

echo "Running initial Alembic migration..."
docker-compose run --rm api alembic -c /api/alembic.ini upgrade head

echo "Setup complete. App running at http://localhost:8000"
