import json
import os
import logging
import uuid
from aiokafka import AIOKafkaProducer, AIOKafkaConsumer
from sqlalchemy import select
from app.models import InboxEventDB

logger = logging.getLogger(__name__)


class KafkaService:
    def __init__(self):
        # Получаем адрес Kafka сервера из переменных окружения
        self.bootstrap_servers = os.getenv(
            "KAFKA_BOOTSTRAP_SERVERS", "kafka.kafka.svc.cluster.local:9092"
        )
        # Названия топиков Kafka
        self.order_events_topic = "student_system-order.events"     # Куда публикуем
        self.shipment_events_topic = "student_system-shipment.events"  # Откуда читаем
    
    async def start(self):
        """Запуск producer и consumer"""
        # Создаем Producer
        self.producer = AIOKafkaProducer(
            bootstrap_servers=self.bootstrap_servers,
            client_id="order-service"
        )
        await self.producer.start()
        
        # Создаем Consumer
        self.consumer = AIOKafkaConsumer(
            self.shipment_events_topic,
            bootstrap_servers=self.bootstrap_servers,
            group_id="order-service-group",
            auto_offset_reset="earliest",  # Читать с начала если нет offset
            enable_auto_commit=True,       # Авто-коммит offset
        )
        await self.consumer.start()
        logger.info("Kafka producer и consumer запущены")
    
    async def stop(self):
        """Остановка producer и consumer"""
        if self.producer:
            await self.producer.stop()
        if self.consumer:
            await self.consumer.stop()
        logger.info("Kafka producer и consumer остановлены")

    async def publish_order_paid(
        self, order_id: str, item_id: str, quantity: int, idempotency_key: str
    ):
        """Публикация события order.paid"""
        if not self.producer:
            raise RuntimeError("Producer не инициализирован. Вызовите start() сначала.")
        
        try:
            # Формируем событие в формате JSON
            event = {
                "event_type": "order.paid",
                "order_id": order_id,
                "item_id": item_id,
                "quantity": str(quantity),  # Преобразуем в строку
                "idempotency_key": idempotency_key,
            }

            # Отправляем событие в Kafka
            await self.producer.send_and_wait(
                topic=self.order_events_topic,
                key=order_id.encode('utf-8'),
                value=json.dumps(event).encode('utf-8'),
            )

            logger.info(f"Опубликовано событие order.paid для заказа {order_id}")
            return True

        except Exception as e:
            logger.error(f"Ошибка публикации в Kafka: {e}")
            return False

    async def consume_shipment_events(self, db):
        """Обработка входящих событий от Shipping Service с Inbox паттерном"""
        if not self.consumer:
            raise RuntimeError("Consumer не инициализирован. Вызовите start() сначала.")
        
        try:
            # получаем сообщения
            async for msg in self.consumer:
                try:
                    # Парсим JSON сообщение
                    event_data = json.loads(msg.value.decode('utf-8'))
                    event_type = event_data.get('event_type')  # Тип события
                    order_id = event_data.get('order_id')      # ID заказа

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

                    # Если событие уже обработано - пропускаем
                    if existing_event:
                        logger.info(f"Событие уже обработано (идемпотентность): {idempotency_key}")
                        continue

                    # Сохраняем событие в таблицу inbox_events для последующей обработки
                    inbox_event = InboxEventDB(
                        id=str(uuid.uuid4()),
                        event_type=event_type,
                        event_data=json.dumps(event_data),
                        order_id=order_id,
                        idempotency_key=idempotency_key,
                        status='pending'
                    )
                    db.add(inbox_event)
                    await db.commit()
                    logger.info(f"Событие сохранено в inbox: {inbox_event.id}")

                except json.JSONDecodeError as e:
                    logger.error(f"Ошибка декодирования JSON: {e}")
                except Exception as e:
                    logger.error(f"Ошибка обработки сообщения: {e}")
                    try:
                        await db.rollback()
                    except:
                        pass

        except Exception as e:
            logger.error(f"Ошибка в consumer loop: {e}")
