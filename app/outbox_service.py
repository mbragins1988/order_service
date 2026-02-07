# app/outbox_service.py
import json
import uuid
from sqlalchemy.orm import Session
from app.models import OutboxEventDB
from app.kafka_service import KafkaService

class OutboxService:
    def __init__(self):
        self.kafka = KafkaService()
    
    def save_and_publish(self, db: Session, event_type: str, event_data: dict, order_id: str):
        """Сохраняем в outbox и сразу публикуем в Kafka"""
        try:
            # 1. Сохраняем в outbox (Outbox паттерн)
            outbox_event = OutboxEventDB(
                id=str(uuid.uuid4()),
                event_type=event_type,
                event_data=json.dumps(event_data),
                order_id=order_id,
                status='published'
            )
            db.add(outbox_event)
            
            # 2. Публикуем в Kafka
            if event_type == "order.paid":
                success = self.kafka.publish_order_paid(
                    order_id=event_data['order_id'],
                    item_id=event_data['item_id'],
                    quantity=int(event_data['quantity']),
                    idempotency_key=event_data['idempotency_key']
                )
                
                if success:
                    outbox_event.status = 'published'
                else:
                    outbox_event.status = 'failed'
            
            return outbox_event
            
        except Exception as e:
            print(f"Ошибка в outbox: {e}")
            raise
