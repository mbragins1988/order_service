import json
import asyncio
import logging
import os
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.database import AsyncSessionLocal
from app.kafka_service import KafkaService
from app.models import OrderDB, OutboxEventDB
from sqlalchemy import select
from app.schemas import NotificationRequest
from app.api import notification


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# logging.basicConfig(level=logging.INFO)

# Каждый воркер создает свой экземпляр KafkaService
kafka_service = KafkaService()


async def outbox_worker():
    """Outbox воркер"""
    logger.info("Outbox worker запущен")
    await kafka_service.producer_start()

    while True:
        try:
            async with AsyncSessionLocal() as db:
                # Ищем pending события
                result = await db.execute(
                    select(OutboxEventDB)
                    .where(OutboxEventDB.status == "pending")
                    .order_by(OutboxEventDB.created_at.asc())
                    .limit(5)
                )
                pending_events = result.scalars().all()

                if pending_events:
                    logger.info(f"Найдено {len(pending_events)} pending событий")

                # Пробуем опубликовать каждое
                for event in pending_events:
                    try:
                        event_data = json.loads(event.event_data)

                        # Только order.paid события
                        if event.event_type == "order.paid":
                            success_kafka = await kafka_service.publish_order_paid(
                                order_id=event_data["order_id"],
                                item_id=event_data["item_id"],
                                quantity=int(event_data["quantity"]),
                                idempotency_key=event_data["idempotency_key"],
                            )
                            logger.info("Попытка отправки сообщения из outbox в брокер")

                            # Получаем order для user_id
                            result = await db.execute(
                                select(OrderDB).where(
                                    OrderDB.id == event_data["order_id"]
                                )
                            )
                            order = result.scalar_one_or_none()
                            if not order:
                                logger.error(
                                    f"Заказ не найден: {event_data['order_id']}"
                                )
                                continue

                            # Отправка уведомления
                            notification_data = NotificationRequest(
                                message="Ваш заказ успешно оплачен и готов к отправке",
                                reference_id=event_data["order_id"],
                                idempotency_key=f"notification_paid_{event_data['order_id']}_{uuid.uuid4()}",
                            )
                            # Вызываем notification и проверяем результат
                            notification_result = await notification(
                                notification_data, order.user_id, db
                            )
                            logger.info("Попытка отправки сообщения пользователю")
                            logger.warning(
                                f"result_notification -  {notification_result}"
                            )
                            # ТОЛЬКО если оба успешны - меняем статус
                            if success_kafka and notification_result:
                                event.status = "published"
                                logger.info(
                                    f"Опубликовано и отправлено уведомление: {event.event_type} для заказа {event.order_id}"
                                )
                            else:
                                logger.warning(
                                    f"Не удалось опубликовать: {event.event_type}"
                                )
                        else:
                            logger.warning(
                                f"Пропускаем неизвестный тип: {event.event_type}"
                            )
                        await session.commit()
                    except Exception as e:
                        logger.error(f"Ошибка обработки события {event.id}: {e}")
                        await db.rollback()  # Откатываем изменения для этого события
                        continue  # Переходим к следующему
                    finally:
                        await session.close()

            # 3. Ждем перед следующей проверкой
            await asyncio.sleep(3)

        except Exception as e:
            logger.error(f"Критическая ошибка воркера: {e}")
            await asyncio.sleep(10)


async def main():
    await outbox_worker()


if __name__ == "__main__":
    asyncio.run(main())
