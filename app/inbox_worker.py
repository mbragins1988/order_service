import logging
import asyncio
import os
import sys
import uuid
from datetime import datetime, timezone
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.models import InboxEventDB, OrderDB, OrderStatus
from app.database import AsyncSessionLocal
from app.schemas import NotificationRequest
from app.api import notification
from sqlalchemy import select

logger = logging.getLogger(__name__)


@staticmethod
async def inbox_worker():
    """Обрабатывает pending события из inbox"""
    logger.info("Inbox worker запущен")
    while True:
        db = AsyncSessionLocal()
        try:
            # Берем события для обработки
            result = await db.execute(
                select(InboxEventDB).where(InboxEventDB.status == "pending")
            )
            pending_events = result.scalars().all()
            for inbox_event in pending_events:
                event_type = inbox_event.event_type
                order_id = inbox_event.order_id
                # Находим и обновляем заказ
                result = await db.execute(select(OrderDB).where(OrderDB.id == order_id))
                order = result.scalar_one_or_none()
                if event_type == "order.shipped":
                    order.status = OrderStatus.SHIPPED
                    logger.info(f"Обработано SHIPPED: {order_id}")
                    inbox_event.status = "processed"
                    inbox_event.processed_at = datetime.now(timezone.utc)
                    # Уведомление об доставке
                    notification_data = NotificationRequest(
                        message="Ваш заказ отправлен в доставку",
                        reference_id=order.id,
                        idempotency_key=f"notification_paid_{order.id}_{uuid.uuid4()}"
                    )
                    user_id = order.user_id
                    await notification(notification_data, user_id, db)
                    logger.info("Отправлено уведомление - 'Ваш заказ отправлен в доставку'")
                elif event_type == "order.cancelled":
                    order.status = OrderStatus.CANCELLED
                    logger.info("Обработано CANCELLED: Доставка невозможна")
                    inbox_event.status = "processed"
                    # Уведомление об отмене
                    notification_data = NotificationRequest(
                        message="Ваш заказ отменен. Причина:",
                        reference_id=order.id,
                        idempotency_key=f"notification_paid_{order.id}_{uuid.uuid4()}"
                    )
            await db.commit()
        except Exception as e:
            logger.error(f"Ошибка inbox worker: {e}")
            await db.rollback()
        finally:
            await db.close()
            await asyncio.sleep(2)


async def main():
    await inbox_worker()


if __name__ == "__main__":
    asyncio.run(main())
