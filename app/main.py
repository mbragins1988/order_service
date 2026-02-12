from fastapi import FastAPI
from contextlib import asynccontextmanager
from app.api import router
from app.kafka_service import KafkaService
from app.database import AsyncSessionLocal
import asyncio
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

kafka_service = KafkaService()

async def run_kafka_consumer():
    """Функция для запуска consumer с постоянной сессией"""
    async with AsyncSessionLocal() as db:
        await kafka_service.consume_shipment_events(db)

@asynccontextmanager
async def lifespan(app: FastAPI):
    await kafka_service.start()
    task = asyncio.create_task(run_kafka_consumer())
    yield
    task.cancel()
    await kafka_service.stop()

app = FastAPI(title="Order Service", lifespan=lifespan)
app.include_router(router, prefix="/api")

@app.get("/health")
async def health():
    return {"status": "healthy"}
