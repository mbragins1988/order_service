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


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


async def inbox_worker():  # Убрал @staticmethod, он здесь не нужен
    """Обрабатывает pending события из inbox"""
    logger.info("Inbox worker запущен")
    while True:
        async with AsyncSessionLocal() as db:
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
                    
                    if not order:
                        logger.error(f"Заказ {order_id} не найден")
                        continue
                    
                    # Обработка в зависимости от типа события
                    if event_type == "order.shipped":
                        # Уведомление о доставке
                        notification_data = NotificationRequest(
                            message="Ваш заказ отправлен в доставку",
                            reference_id=order.id,
                            idempotency_key=f"notification_shipped_{order.id}_{uuid.uuid4()}"
                        )
                        
                        success_notification_shipped = await notification(notification_data, order.user_id, db)
                        logger.warning("result_notification - ", success_notification_shipped) 
                        if success_notification_shipped:
                            order.status = OrderStatus.SHIPPED
                            inbox_event.status = "processed"
                            inbox_event.processed_at = datetime.now(timezone.utc)
                            logger.info("Обработано SHIPPED, уведомление отправлено")
                        else:
                            logger.warning("Уведомление не отправлено, событие останется pending")
                    
                    elif event_type == "order.cancelled":
                        reason = inbox_event.event_data.get("reason", "неизвестная причина")
                        
                        # Уведомление об отмене
                        notification_data = NotificationRequest(
                            message=f"Ваш заказ отменен. Причина: {reason}",
                            reference_id=order.id,
                            idempotency_key=f"notification_cancelled_{order.id}_{uuid.uuid4()}"
                        )
                        
                        success_notification_canceled = await notification(notification_data, order.user_id, db)
                        
                        if success_notification_canceled:
                            order.status = OrderStatus.CANCELLED
                            inbox_event.status = "processed"
                            inbox_event.processed_at = datetime.now(timezone.utc)
                            logger.info(f"Обработано CANCELLED: {order_id}, уведомление отправлено")
                        else:
                            logger.warning("Уведомление не отправлено, событие останется pending")
                    
                    await db.commit()
                    
            except Exception as e:
                logger.error(f"Ошибка inbox worker: {e}")
                await db.rollback()
            
            await asyncio.sleep(2)


async def main():
    await inbox_worker()


if __name__ == "__main__":
    asyncio.run(main())
