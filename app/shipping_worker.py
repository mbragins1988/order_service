import asyncio
import logging
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.database import AsyncSessionLocal
from app.kafka_service import KafkaService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def shipping_consumer_worker():
    """Worker для чтения событий от Shipping Service"""
    logger.info("Shipping consumer worker запущен")

    kafka_service = KafkaService()

    while True:
        try:
            async with AsyncSessionLocal() as db:
                await kafka_service.consume_shipment_events(db)

            await asyncio.sleep(1)

        except Exception as e:
            logger.error(f"Ошибка в shipping consumer: {e}")
            await asyncio.sleep(5)


async def main():
    await shipping_consumer_worker()


if __name__ == "__main__":
    asyncio.run(main())
