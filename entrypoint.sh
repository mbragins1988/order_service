#!/bin/bash
set -e

export PYTHONUNBUFFERED=1 
echo "Applying database migrations"
alembic upgrade head

# echo "Starting workers..."
python -m app.presentation.outbox_worker &
python -m app.presentation.inbox_worker &
python -m app.presentation.shipping_consumer &

echo "Starting FastAPI application..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
