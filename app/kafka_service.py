import json
import os
import logging
from confluent_kafka import Producer, Consumer
from sqlalchemy import select
from app.models import InboxEventDB
import uuid


logger = logging.getLogger(__name__)  # Создаем логгер для этого модуля


class KafkaService:
    def __init__(self):
        # Получаем адрес Kafka сервера из переменных окружения
        self.bootstrap_servers = os.getenv(
            "KAFKA_BOOTSTRAP_SERVERS", "kafka.kafka.svc.cluster.local:9092"
        )
        # Названия топиков Kafka
        self.order_events_topic = "student_system-order.events"     # Куда публикуем
        self.shipment_events_topic = "student_system-shipment.events"  # Откуда читаем

        # Создаем Producer
        self.producer = Producer(
            {"bootstrap.servers": self.bootstrap_servers,
             "client.id": "order-service"}
        )

        # Создаем Consumer
        self.consumer = Consumer(
            {
                "bootstrap.servers": self.bootstrap_servers,  # Адрес Kafka
                "group.id": "order-service-group",            # Группа потребителей
                "auto.offset.reset": "earliest",              # Читать с начала если нет offset
                "enable.auto.commit": True,                   # Авто-коммит offset
            }
        )
        # Подписываемся на топик shipment_events_topic
        self.consumer.subscribe([self.shipment_events_topic])

    async def publish_order_paid(
        self, order_id: str, item_id: str, quantity: int, idempotency_key: str
    ):
        """Публикация события order.paid"""
        try:
            # Формируем событие в формате JSON
            event = {
                "event_type": "order.paid",  # Тип события
                "order_id": order_id,        # ID заказа
                "item_id": item_id,          # ID товара
                "quantity": str(quantity),   # Количество (преобразуем в строку)
                "idempotency_key": idempotency_key,  # Ключ идемпотентности
            }

            # 50-54: Отправляем событие в Kafka
            await self.producer.send_and_wait(
                topic=self.order_events_topic,  # В какой топик
                key=order_id.encode('utf-8'),   # Ключ сообщения (для партиционирования)
                value=json.dumps(event).encode('utf-8'),  # Значение (событие в JSON)
            )

            # 56: Логируем успешную отправку
            logger.info(f"Опубликовано событие order.paid для заказа {order_id}")
            return True

        except Exception as e:
            # 59-60: Логируем ошибку
            logger.error(f"Ошибка публикации в Kafka: {e}")
            return False

    async def consume_shipment_events(self, db):
        """Обработка входящих событий от Shipping Service с Inbox паттерном"""
        try:
            # 67-68: Получаем одно сообщение из Kafka (асинхронно)
            msg = await self.consumer.getone()

            # 70-72: Проверяем на ошибки
            if msg.error():
                logger.error(f"Ошибка consumer: {msg.error()}")
                return

            # 75-77: Парсим JSON сообщение
            event_data = json.loads(msg.value().decode('utf-8'))
            event_type = event_data.get('event_type')  # Тип события (order.shipped/cancelled)
            order_id = event_data.get('order_id')      # ID заказа

            # 79: Логируем полученное событие
            logger.info(f"Получено событие: {event_type} для заказа {order_id}")

            # 82: Генерируем ключ идемпотентности
            idempotency_key = f"{event_type}_{order_id}"

            # 85-90: Проверяем в БД, не обрабатывали ли уже это событие
            result = await db.execute(
                select(InboxEventDB).where(
                    InboxEventDB.idempotency_key == idempotency_key
                )
            )
            existing_event = result.scalar_one_or_none()  # Ищем существующее событие

            # 92-96: Если событие уже обработано - выходим (идемпотентность)
            if existing_event:
                logger.info(f"Событие уже обработано (идемпотентность): {idempotency_key}")
                return  # Уже обработали, выходим

            # 99-106: Сохраняем событие в таблицу inbox_events для последующей обработки
            inbox_event = InboxEventDB(
                id=str(uuid.uuid4()),           # Генерируем уникальный ID
                event_type=event_type,          # Тип события
                event_data=json.dumps(event_data),  # Данные события в JSON
                order_id=order_id,              # ID заказа
                idempotency_key=idempotency_key,  # Ключ идемпотентности
                status='pending'                # Статус: ожидает обработки
            )
            db.add(inbox_event)      # Добавляем в сессию
            await db.commit()        # Сохраняем в БД
            logger.info(f"Событие сохранено в inbox: {inbox_event.id}")

        except Exception as e:
            # 113-115: Логируем ошибку и откатываем транзакцию если была
            logger.error(f"Ошибка обработки Kafka сообщения: {e}")
            if 'db' in locals():
                await db.rollback()  # Откатываем изменения в БД