import logging
import json
from pydantic import BaseModel
from typing import Optional

from app.domain.models import OrderStatus
from app.domain.exceptions import OrderNotFoundError

logger = logging.getLogger(__name__)


class PaymentCallbackDTO(BaseModel):
    payment_id: str
    order_id: str
    status: str
    amount: str
    error_message: Optional[str] = None


class ProcessPaymentCallbackUseCase:
    def __init__(self, unit_of_work):
        self._uow = unit_of_work

    async def __call__(self, dto: PaymentCallbackDTO) -> None:
        logger.info(f"Обработка payment callback: {dto}")

        async with self._uow() as uow:
            order = await uow.orders.get_by_id(dto.order_id)
            if not order:
                raise OrderNotFoundError(f"Заказ {dto.order_id} не найден")

            # Идемпотентность
            if order.status == OrderStatus.PAID and dto.status == "succeeded":
                logger.info(f"Заказ {order.id} уже обработан")
                return

            # Обработка успешного платежа
            if dto.status == "succeeded" and order.can_be_paid():
                await uow.orders.update_status(dto.order_id, OrderStatus.PAID)

                # Событие для Shipping Service
                await uow.outbox.create(
                    event_type="order.paid",
                    event_data={
                        "order_id": dto.order_id,
                        "item_id": order.item_id,
                        "quantity": order.quantity,
                        "idempotency_key": f"order_paid_{dto.order_id}"
                    },
                    order_id=dto.order_id
                )

                # Уведомление об успешной оплате
                await uow.outbox.create(
                    event_type="notification.send",
                    event_data={
                        "user_id": order.user_id,
                        "message": "Ваш заказ успешно оплачен и готов к отправке",
                        "reference_id": dto.order_id
                    },
                    order_id=dto.order_id
                )

                logger.info(f"Заказ {dto.order_id} отмечен PAID")

            # Обработка неуспешного платежа
            elif dto.status == "failed":
                await uow.orders.update_status(dto.order_id, OrderStatus.CANCELLED)

                # Уведомление об отмене
                error_msg = dto.error_message or "платеж не прошел"
                await uow.outbox.create(
                    event_type="notification.send",
                    event_data={
                        "user_id": order.user_id,
                        "message": f"Ваш заказ отменен. Причина: {error_msg}",
                        "reference_id": dto.order_id
                    },
                    order_id=dto.order_id
                )

                logger.info(f"Заказ {dto.order_id} отменен из-за неудачного платежа")

            # Сохраняем payment_id, если его нет
            if not order.payment_id:
                await uow.orders.update_payment_id(dto.order_id, dto.payment_id)

            await uow.commit()
