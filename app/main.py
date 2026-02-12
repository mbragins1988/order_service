from fastapi import FastAPI
from contextlib import asynccontextmanager
from app.api import router
from app.kafka_service import KafkaService
import logging
import asyncio

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

kafka_service = KafkaService()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: запускаем Kafka
    logger.info("Запуск Kafka producer и consumer...")
    await kafka_service.start()
    
    # ✅ Просто запускаем consumer как фоновую задачу (ОДИН РАЗ)
    from app.database import AsyncSessionLocal
    consumer_task = asyncio.create_task(
        kafka_service.consume_shipment_events(AsyncSessionLocal())
    )
    
    logger.info("Order Service запущен")
    yield
    
    # Shutdown: останавливаем Kafka
    logger.info("Остановка Kafka...")
    consumer_task.cancel()
    await kafka_service.stop()

app = FastAPI(
    title="Order Service",
    version="3.0.0",
    lifespan=lifespan
)

app.include_router(router, prefix="/api")
