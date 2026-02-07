# app/kafka_worker.py
import time
import logging
from app.database import SessionLocal
from app.kafka_service import KafkaService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_kafka_consumer():
    """Запуск Kafka consumer в фоновом режиме"""
    logger.info("Запуск Kafka consumer...")
    
    kafka_service = KafkaService()
    
    while True:
        try:
            db = SessionLocal()
            try:
                # Обрабатываем входящие сообщения
                kafka_service.consume_shipment_events(db)
                db.commit()
            except Exception as e:
                logger.error(f"Ошибка БД: {e}")
                db.rollback()
            finally:
                db.close()
            
            time.sleep(1)  # Пауза между проверками
            
        except Exception as e:
            logger.error(f"Ошибка в Kafka worker: {e}")
            time.sleep(5)
