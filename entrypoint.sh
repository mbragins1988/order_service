#!/bin/bash
set -e

export PYTHONUNBUFFERED=1 
echo "Applying database migrations..."
echo "POSTGRES_CONNECTION_STRING: $POSTGRES_CONNECTION_STRING"
echo "POSTGRES_DATABASE_NAME: $POSTGRES_DATABASE_NAME"
echo "POSTGRES_HOST: $POSTGRES_HOST"
echo "POSTGRES_PORT: $POSTGRES_PORT"
echo "POSTGRES_USERNAME: $POSTGRES_USERNAME"
echo "POSTGRES_PASSWORD: $POSTGRES_PASSWORD"
echo "==================================="
alembic upgrade head

# echo "Starting workers..."
python -m app.outbox_worker &
python -m app.inbox_worker &
python -m app.shipping_worker &

echo "Starting FastAPI application..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
