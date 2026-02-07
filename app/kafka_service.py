# app/kafka_service.py
import json
import os
import logging
from typing import Dict, Any
from confluent_kafka import Producer, Consumer

logger = logging.getLogger(__name__)


class KafkaService:
    def __init__(self):
        self.bootstrap_servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka.kafka.svc.cluster.local:9092")
        self.order_events_topic = "student_system-order.events"
        self.shipment_events_topic = "student_system-shipment.events"
        
        # Производитель
        self.producer = Producer({
            'bootstrap.servers': self.bootstrap_servers,
            'client.id': 'order-service'
        })
        
        # Потребитель
        self.consumer = Consumer({
            'bootstrap.servers': self.bootstrap_servers,
            'group.id': 'order-service-group',
            'auto.offset.reset': 'earliest',
            'enable.auto.commit': True
        })
        self.consumer.subscribe([self.shipment_events_topic])
    
    def publish_order_paid(self, order_id: str, item_id: str, quantity: int, idempotency_key: str):
        """Публикация события order.paid"""
        try:
            event = {
                "event_type": "order.paid",
                "order_id": order_id,
                "item_id": item_id,
                "quantity": str(quantity),  # Важно: строка!
                "idempotency_key": idempotency_key
            }
            
            self.producer.produce(
                topic=self.order_events_topic,
                key=order_id.encode('utf-8'),
                value=json.dumps(event).encode('utf-8')
            )
            self.producer.flush()
            
            logger.info(f"Опубликовано событие order.paid для заказа {order_id}")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка публикации в Kafka: {e}")
            return False
    
    def consume_shipment_events(self, db):
        """Обработка входящих событий от Shipping Service"""
        try:
            msg = self.consumer.poll(1.0)
            
            if msg is None:
                return
            if msg.error():
                logger.error(f"Ошибка consumer: {msg.error()}")
                return
            
            # Парсим сообщение
            event_data = json.loads(msg.value().decode('utf-8'))
            event_type = event_data.get('event_type')
            order_id = event_data.get('order_id')
            
            logger.info(f"Получено событие: {event_type} для заказа {order_id}")
            
            # Обрабатываем событие
            from app.models import OrderDB, OrderStatus
            
            order = db.query(OrderDB).filter(OrderDB.id == order_id).first()
            if not order:
                logger.error(f"Заказ {order_id} не найден")
                return
            
            if event_type == "order.shipped":
                order.status = OrderStatus.SHIPPED
                logger.info(f"Статус заказа {order_id} обновлен на SHIPPED")
            
            elif event_type == "order.cancelled":
                order.status = OrderStatus.CANCELLED
                logger.info(f"Статус заказа {order_id} обновлен на CANCELLED")
            
            else:
                logger.warning(f"Неизвестный тип события: {event_type}")
                return
            
            db.commit()
            
        except Exception as e:
            logger.error(f"Ошибка обработки Kafka сообщения: {e}")
