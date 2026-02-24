import asyncio
import logging
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.database import AsyncSessionLocal
from app.infrastructure.unit_of_work import UnitOfWork
from app.infrastructure.http_clients import HTTPNotificationsClient
from app.infrastructure.kafka_producer import KafkaProducerClient
from app.application.process_outbox import ProcessOutboxEventsUseCase
from app.config import settings

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def outbox_worker():
    """Worker для обработки outbox событий"""
    logger.info("Outbox worker started")

    # Инициализация зависимостей
    kafka_producer = KafkaProducerClient(settings.KAFKA_BOOTSTRAP_SERVERS)
    await kafka_producer.start()

    notifications_client = HTTPNotificationsClient(settings.CATALOG_BASE_URL, settings.API_TOKEN)

    # Use case
    use_case = ProcessOutboxEventsUseCase(
        unit_of_work=lambda: UnitOfWork(AsyncSessionLocal),
        kafka_producer=kafka_producer,
        notifications_client=notifications_client
    )

    try:
        while True:
            try:
                processed = await use_case(limit=5)
                if processed:
                    logger.info(f"Processed {processed} outbox events")
                await asyncio.sleep(3)
            except Exception as e:
                logger.error(f"Error in outbox worker cycle: {e}")
                await asyncio.sleep(10)
    finally:
        await kafka_producer.stop()


async def main():
    await outbox_worker()


if __name__ == "__main__":
    asyncio.run(main())
