import json
import os
import logging
from confluent_kafka import Producer, Consumer
from sqlalchemy import select
from app.models import InboxEventDB
import uuid

logger = logging.getLogger(__name__)


class KafkaService:
    def __init__(self):
        self.bootstrap_servers = os.getenv(
            "KAFKA_BOOTSTRAP_SERVERS", "kafka.kafka.svc.cluster.local:9092"
        )
        self.order_events_topic = "student_system-order.events"
        self.shipment_events_topic = "student_system-shipment.events"

        self.producer = Producer(
            {"bootstrap.servers": self.bootstrap_servers, "client.id": "order-service"}
        )

        self.consumer = Consumer(
            {
                "bootstrap.servers": self.bootstrap_servers,
                "group.id": "order-service-group",
                "auto.offset.reset": "earliest",
                "enable.auto.commit": True,
            }
        )
        self.consumer.subscribe([self.shipment_events_topic])

    async def publish_order_paid(
        self, order_id: str, item_id: str, quantity: int, idempotency_key: str
    ):
        """Публикация события order.paid"""
        try:
            event = {
                "event_type": "order.paid",
                "order_id": order_id,
                "item_id": item_id,
                "quantity": str(quantity),
                "idempotency_key": idempotency_key,
            }

            await self.producer.send_and_wait(
                topic=self.order_events_topic,
                key=order_id.encode("utf-8"),
                value=json.dumps(event).encode("utf-8"),
            )

            logger.info(f"Опубликовано событие order.paid для заказа {order_id}")
            return True

        except Exception as e:
            logger.error(f"Ошибка публикации в Kafka: {e}")
            return False

    async def consume_shipment_events(self, db):
        """Обработка входящих событий от Shipping Service с Inbox паттерном"""
        try:
            # Асинхронное получение сообщения
            msg = await self.consumer.getone()

            if msg.error():
                logger.error(f"Ошибка consumer: {msg.error()}")
                return

            # Парсим сообщение
            event_data = json.loads(msg.value().decode("utf-8"))
            event_type = event_data.get("event_type")
            order_id = event_data.get("order_id")

            logger.info(f"Получено событие: {event_type} для заказа {order_id}")

            # Проверяем идемпотентность. Генерируем уникальный ключ для события
            idempotency_key = f"{event_type}_{order_id}"

            # Проверяем, не обрабатывали ли уже это событие
            result = await db.execute(
                select(InboxEventDB).where(
                    InboxEventDB.idempotency_key == idempotency_key
                )
            )
            existing_event = result.scalar_one_or_none()

            if existing_event:
                logger.info(
                    f"Событие уже обработано (идемпотентность): {idempotency_key}"
                )
                return  # Уже обработали, выходим

            # Сохраняем в inbox перед обработкой
            inbox_event = InboxEventDB(
                id=str(uuid.uuid4()),
                event_type=event_type,
                event_data=json.dumps(event_data),
                order_id=order_id,
                idempotency_key=idempotency_key,
                status="pending",
            )
            db.add(inbox_event)
            await db.commit()
            logger.info(f"Событие сохранено в inbox: {inbox_event.id}")

        except Exception as e:
            logger.error(f"Ошибка обработки Kafka сообщения: {e}")
            if "db" in locals():
                await db.rollback()
