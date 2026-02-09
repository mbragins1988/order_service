import logging
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.models import InboxEventDB, OrderDB, OrderStatus
from app.database import AsyncSessionLocal
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
                elif event_type == "order.cancelled":
                    order.status = OrderStatus.CANCELLED
                    logger.info(f"Обработано CANCELLED: {order_id}")
                    inbox_event.status = "processed"
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
