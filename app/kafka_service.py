import json
import os
import sys
import logging
import uuid
from aiokafka import AIOKafkaProducer, AIOKafkaConsumer
from sqlalchemy import select

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.models import InboxEventDB

logger = logging.getLogger(__name__)


class KafkaService:
    def __init__(self):
        self.bootstrap_servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS")
        self.order_events_topic = "student_system-order.events"
        self.shipment_events_topic = "student_system-shipment.events"
    
    async def producer_start(self):
        """Запуск producer"""
        self.producer = AIOKafkaProducer(
            bootstrap_servers=self.bootstrap_servers,
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )
        await self.producer.start()
        logger.info(f"Kafka producer запущен (pid: {os.getpid()})")

    async def consumer_start(self):
        """Запуск consumer"""

        self.consumer = AIOKafkaConsumer(
            self.shipment_events_topic,
            bootstrap_servers=self.bootstrap_servers,
            value_deserializer=lambda v: json.loads(v.decode('utf-8'))
        )
        await self.consumer.start()
        self._started = True
        logger.info(f"Kafka consumer запущен (pid: {os.getpid()})")
    
    async def stop(self):
        """Остановка producer и consumer"""
        if self.producer:
            await self.producer.stop()
        if self.consumer:
            await self.consumer.stop()
        self._started = False
        logger.info(f"Kafka остановлен (pid: {os.getpid()})")

    async def publish_order_paid(
        self, order_id: str, item_id: str, quantity: int, idempotency_key: str
    ):
        try:
            # Формируем событие в формате JSON
            event = {
                "event_type": "order.paid",
                "order_id": order_id,
                "item_id": item_id,
                "quantity": str(quantity),
                "idempotency_key": idempotency_key,
            }
            
            # Отправляем событие в Kafka
            await self.producer.send_and_wait(
                topic=self.order_events_topic,
                key=order_id,
                value=event,
            )
            logger.info(f"Опубликовано событие order.paid для заказа {order_id}")
            return True

        except Exception as e:
            logger.error(f"Ошибка публикации в Kafka: {e}")
            return False

    async def consume_shipment_events(self, db):
        """Обработка входящих событий от Shipping Service с Inbox паттерном"""

        try:
            async for msg in self.consumer:
                try:
                    event_data = msg.value  # Уже десериализовано
                    event_type = event_data.get('event_type')
                    order_id = event_data.get('order_id')

                    logger.info(f"Получено событие: {event_type} для заказа {order_id}")

                    # Генерируем ключ идемпотентности
                    idempotency_key = f"{event_type}_{order_id}"

                    # Проверяем в БД, не обрабатывали ли уже это событие
                    result = await db.execute(
                        select(InboxEventDB).where(
                            InboxEventDB.idempotency_key == idempotency_key
                        )
                    )
                    existing_event = result.scalar_one_or_none()

                    if existing_event:
                        logger.info(f"Событие уже обработано: {idempotency_key}")
                        await self.consumer.commit()
                        continue

                    # Сохраняем событие в таблицу inbox_events
                    inbox_event = InboxEventDB(
                        id=str(uuid.uuid4()),
                        event_type=event_type,
                        event_data=event_data,
                        order_id=order_id,
                        idempotency_key=idempotency_key,
                        status='pending'
                    )
                    db.add(inbox_event)
                    await db.commit()
                    
                    # Коммитим offset после успешной обработки
                    await self.consumer.commit()
                    logger.info(f"Событие сохранено в inbox: {inbox_event.id}")

                except Exception as e:
                    logger.error(f"Ошибка обработки сообщения: {e}")
                    await db.rollback()

        except Exception as e:
            logger.error(f"Ошибка в consumer loop: {e}")
