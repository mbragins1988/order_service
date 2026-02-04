#!/bin/bash
# entrypoint.sh
set -e

echo "=== Starting Order Service ==="
echo "Environment:"
env | grep -E "POSTGRES|DATABASE" || echo "No DB env vars found"

echo "Applying database migrations..."
alembic upgrade head

echo "Starting FastAPI application..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
