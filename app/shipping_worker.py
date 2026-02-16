import asyncio
import logging
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.database import AsyncSessionLocal
from app.kafka_service import KafkaService

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

kafka_service = KafkaService()


async def shipping_consumer_worker():
    """Worker для чтения событий от Shipping Service"""
    logger.info("Shipping consumer worker запущен")
    
    try:
        # Запускаем Kafka (создает consumer)
        await kafka_service.consumer_start()
        
        # Начинаем читать события - это бесконечный цикл!
        async with AsyncSessionLocal() as db:
            await kafka_service.consume_shipment_events(db)
            
    except Exception as e:
        logger.error(f"Ошибка в shipping consumer: {e}")


async def main():
    await shipping_consumer_worker()


if __name__ == "__main__":
    asyncio.run(main())
