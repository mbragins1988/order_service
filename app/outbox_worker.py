import json
import asyncio
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.database import AsyncSessionLocal
from app.kafka_service import KafkaService
from app.models import OutboxEventDB
from sqlalchemy import select

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def outbox_worker():
    """Outbox воркер"""
    logger.info("Outbox worker запущен")

    kafka_service = KafkaService()

    while True:
        try:
            async with AsyncSessionLocal() as db:
                # 1. Ищем pending события
                result = await db.execute(
                    select(OutboxEventDB)
                    .where(OutboxEventDB.status == "pending")
                    .order_by(OutboxEventDB.created_at.asc())
                    .limit(5)
                )
                pending_events = result.scalars().all()

                if pending_events:
                    logger.info(f"Найдено {len(pending_events)} pending событий")

                # 2. Пробуем опубликовать каждое
                for event in pending_events:
                    try:
                        event_data = json.loads(event.event_data)

                        # Только order.paid события
                        if event.event_type == "order.paid":
                            success = await kafka_service.publish_order_paid(
                                order_id=event_data["order_id"],
                                item_id=event_data["item_id"],
                                quantity=int(event_data["quantity"]),
                                idempotency_key=event_data["idempotency_key"],
                            )

                            if success:
                                event.status = "published"
                                logger.info(
                                    f"Опубликовано: {event.event_type} для заказа {event.order_id}"
                                )
                            else:
                                logger.warning(
                                    f"Не удалось опубликовать: {event.event_type}"
                                )
                        else:
                            logger.warning(
                                f"Пропускаем неизвестный тип: {event.event_type}"
                            )

                    except Exception as e:
                        logger.error(f"Ошибка обработки события {event.id}: {e}")

                await db.commit()

            # 3. Ждем перед следующей проверкой
            await asyncio.sleep(3)

        except Exception as e:
            logger.error(f"Критическая ошибка воркера: {e}")
            await asyncio.sleep(10)


async def main():
    await outbox_worker()


if __name__ == "__main__":
    asyncio.run(main())
