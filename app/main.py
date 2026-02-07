# app/main.py
import threading
from fastapi import FastAPI
from contextlib import asynccontextmanager
from app.api import router
from app.kafka_worker import run_kafka_consumer
from app.database import engine, Base
from app.models import OrderDB, OutboxEventDB, InboxEventDB
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Управление жизненным циклом приложения"""
    # 1. Создаем таблицы
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Таблицы созданы")
    except Exception as e:
        logger.info(f"Таблицы уже существуют: {e}")
    
    # 2. Запускаем Kafka consumer в фоне
    kafka_thread = threading.Thread(target=run_kafka_consumer, daemon=True)
    kafka_thread.start()
    logger.info("Kafka consumer запущен")
    
    yield
    
    logger.info("Приложение останавливается...")

app = FastAPI(
    title="Order Service",
    description="Сервис заказов с Kafka",
    version="3.0.0",
    lifespan=lifespan
)

app.include_router(router, prefix="/api")

@app.get("/")
async def root():
    return {"message": "Order Service с Kafka работает"}

@app.get("/health")
async def health():
    return {"status": "healthy", "kafka": "running"}
