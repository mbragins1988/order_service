import logging
from datetime import datetime, timezone

from app.domain.models import OrderStatus

logger = logging.getLogger(__name__)


class ProcessInboxEventsUseCase:
    def __init__(self, unit_of_work, notifications_client):
        self._uow = unit_of_work
        self._notifications_client = notifications_client

    async def __call__(self, limit: int = 10) -> int:
        """Обрабатывает pending события из inbox. Возвращает количество обработанных."""

        async with self._uow() as uow:
            # Получаем pending события
            pending = await uow.inbox.get_pending(limit=limit)

            if not pending:
                return 0

            logger.info(f"Обработка {len(pending)} inbox events")

            for event in pending:
                try:
                    event_id = event["id"]
                    event_type = event["event_type"]
                    order_id = event["order_id"]
                    event_data = event["event_data"]

                    # Находим заказ
                    order = await uow.orders.get_by_id(order_id)
                    if not order:
                        logger.error(f"Заказ {order_id} не найден для inbox event {event_id}")
                        await uow.inbox.mark_as_failed(event_id)
                        continue

                    # Обработка order.shipped
                    if event_type == "order.shipped":
                        if order.can_be_shipped():
                            await uow.orders.update_status(order_id, OrderStatus.SHIPPED)
                            logger.info(f"Заказ {order_id} отмечен SHIPPED")
                            # Помечаем inbox как обработанный
                            await uow.inbox.mark_as_processed(event_id)
                            # Уведомление
                            notifications = await self._notifications.send(
                                message="Ваш заказ отправлен в доставку (SHIPPED)",
                                reference_id=order.id,
                                idempotency_key=f"notification_created_{order.idempotency_key}",
                                user_id=order.user_id
                            )
                            if notifications:
                                logger.info(f"Отправлено уведомление 'Ваш заказ отправлен в доставку (SHIPPED)' для {order.id}")
                            else:
                                logger.info(f"Не отправлено уведомление 'Ваш заказ отправлен в доставку (SHIPPED)' для {order.id}")
                        else:
                            logger.warning(f"Заказ {order_id} не может быть доставлен (status: {order.status})")

                    # Обработка order.cancelled
                    elif event_type == "order.cancelled":
                        if order.can_be_cancelled():
                            await uow.orders.update_status(order_id, OrderStatus.CANCELLED)

                            reason = event_data.get("reason", "неизвестная причина")
                            await uow.outbox.create(
                                event_type="notification.send",
                                event_data={
                                    "user_id": order.user_id,
                                    "message": f"Ваш заказ отменен. Причина: {reason}",
                                    "reference_id": order_id
                                },
                                order_id=order_id
                            )
                            logger.info(f"Заказ {order_id} отмечен CANCELLED")
                            # Уведомление
                            notifications = await self._notifications.send(
                                message=f"Ваш заказ отменен (CANCELLED). Причина: {reason}",
                                reference_id=order.id,
                                idempotency_key=f"notification_created_{order.idempotency_key}",
                                user_id=order.user_id
                            )
                            if notifications:
                                logger.info(f"Отправлено уведомление 'Ваш заказ отменен (CANCELLED)' для {order.id}")
                            else:
                                logger.info(f"Не отправлено уведомление 'Ваш заказ отменен (CANCELLED)' для {order.id}")
                        else:
                            logger.warning(f"Заказ {order_id} не может быть отменен (status: {order.status})")

                except Exception as e:
                    logger.error(f"Ошибка обработки inbox event {event['id']}: {e}")

            await uow.commit()

        return True
