set -e

echo "Applying database migrations..."
alembic upgrade head

echo "Starting workers..."
python -m app.outbox_worker &
python -m app.inbox_worker &
python -m app.shipping_worker &

echo "Starting FastAPI application..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
