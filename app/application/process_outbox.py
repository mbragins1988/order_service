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
        processed = 0

        async with self._uow() as uow:
            # Получаем pending события
            pending = await uow.outbox.get_pending(limit=limit)

            if not pending:
                return 0

            logger.info(f"Processing {len(pending)} outbox events")

            for event in pending:
                try:
                    event_data = event["event_data"]
                    if isinstance(event_data, str):
                        event_data = json.loads(event_data)

                    # Обработка order.paid событий
                    if event["event_type"] == "order.paid":
                        success = await self._kafka.publish_order_paid(
                            order_id=event_data["order_id"],
                            item_id=event_data["item_id"],
                            quantity=event_data["quantity"],
                            idempotency_key=event_data["idempotency_key"]
                        )

                        if success:
                            await uow.outbox.mark_as_published(event["id"])
                            processed += 1
                            logger.info(f"Published order.paid event {event['id']}")

                    # Обработка уведомлений
                    elif event["event_type"] == "notification.send":
                        success = await self._notifications.send(
                            message=event_data["message"],
                            reference_id=event_data["reference_id"],
                            idempotency_key=f"notification_{event['id']}",
                            user_id=event_data["user_id"]
                        )

                        if success:
                            await uow.outbox.mark_as_published(event["id"])
                            processed += 1
                            logger.info(f"Sent notification event {event['id']}")

                except Exception as e:
                    logger.error(f"Error processing outbox event {event['id']}: {e}")

            await uow.commit()

        return processed
