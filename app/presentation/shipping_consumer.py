import asyncio
import logging
import sys
import os
import uuid
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.database import AsyncSessionLocal
from app.infrastructure.kafka_consumer import KafkaConsumerClient
from app.infrastructure.repositories import SQLAlchemyInboxRepository
from app.config import settings

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def handle_shipment_event(event_data: dict):
    """Сохраняет событие от Shipping Service в inbox"""
    event_type = event_data.get("event_type")
    order_id = event_data.get("order_id")
    idempotency_key = f"{event_type}_{order_id}"

    logger.info(f"Получено {event_type} для заказа {order_id}")

    async with AsyncSessionLocal() as db:
        inbox_repo = SQLAlchemyInboxRepository(db)

        # Проверяем, не обрабатывали ли уже
        if await inbox_repo.is_processed(idempotency_key):
            logger.info(f"Событие {idempotency_key} уже обработано")
            return

        # Сохраняем в inbox
        await inbox_repo.create(
            event_type=event_type,
            event_data=event_data,
            order_id=order_id,
            idempotency_key=idempotency_key
        )
        await db.commit()
        logger.info(f"Сохранено {event_type} inbox для заказа {order_id}")


async def shipping_consumer():
    """Consumer для событий от Shipping Service"""
    logger.info("Shipping consumer started")

    consumer = KafkaConsumerClient(settings.KAFKA_BOOTSTRAP_SERVERS)
    await consumer.start()

    try:
        await consumer.consume(handle_shipment_event)
    finally:
        await consumer.stop()


async def main():
    await shipping_consumer()


if __name__ == "__main__":
    asyncio.run(main())
