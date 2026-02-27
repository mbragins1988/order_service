import logging
import json

logger = logging.getLogger(__name__)


class ProcessOutboxEventsUseCase:
    def __init__(self, unit_of_work, kafka_producer, notifications_client):
        self._uow = unit_of_work
        self._kafka = kafka_producer
        self._notifications = notifications_client

    async def __call__(self, limit: int = 5) -> int:
        """Обрабатывает pending события из outbox. Возвращает количество обработанных."""

        async with self._uow() as uow:  # создается сессия
            pending = await uow.outbox.get_pending(limit=limit)

            for event in pending:
                try:
                    event_data = event["event_data"]
                    if isinstance(event_data, str):
                        event_data = json.loads(event_data)

                    # Обработка order.paid событий
                    if event["event_type"] == "order.paid":
                        # Получаем заказ
                        order = await uow.orders.get_by_id(event_data["order_id"])
                        logger.error(f"В outbox найден заказ {order}")
                        if not order:
                            logger.error(f"Заказ {event_data['order_id']} не найден")
                            continue
                        success = await self._kafka.publish_order_paid(
                            order_id=event_data["order_id"],
                            item_id=event_data["item_id"],
                            quantity=event_data["quantity"],
                            idempotency_key=event_data["idempotency_key"]
                        )
                        logger.error(f"Попытка отправки в Кафка {success}")

                        # Обработка уведомлений
                        notifications = await self._notifications.send(
                            message="Ваш заказ успешно оплачен (PAID) и готов к отправке",
                            reference_id=event_data["order_id"],
                            idempotency_key=f"notification_{event['id']}",
                            user_id=order.user_id
                        )
                        if success and notifications:
                            await uow.outbox.mark_as_published(event["id"])
                            logger.info(f"Опубликовано order.paid event {event['id']}")
                            logger.info(f"Отправлено уведомление 'Ваш заказ успешно оплачен (PAID) и готов к отправке' для {event['id']}")
                        else:
                            logger.info(f"Неуспешная отправка в Кафка {success}")
                except Exception as e:
                    logger.error(f"Ошибка обработки outbox event {event['id']}: {e}")

            await uow.commit()

        return True
