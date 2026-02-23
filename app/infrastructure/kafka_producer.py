import json
import logging
from aiokafka import AIOKafkaProducer

logger = logging.getLogger(__name__)


class KafkaProducerClient:
    def __init__(self, bootstrap_servers: str):
        self._bootstrap_servers = bootstrap_servers
        self._producer: AIOKafkaProducer | None = None
        self._topic = "student_system-order.events"

    async def start(self):
        if not self._producer:
            self._producer = AIOKafkaProducer(
                bootstrap_servers=self._bootstrap_servers
            )
            await self._producer.start()
            logger.info("Kafka producer started")

    async def stop(self):
        if self._producer:
            await self._producer.stop()
            self._producer = None
            logger.info("Kafka producer stopped")

    async def publish_order_paid(self, order_id: str, item_id: str, quantity: int, idempotency_key: str) -> bool:
        if not self._producer:
            logger.error("Kafka producer not started")
            return False

        try:
            event = {
                "event_type": "order.paid",
                "order_id": order_id,
                "item_id": item_id,
                "quantity": quantity,
                "idempotency_key": idempotency_key
            }

            await self._producer.send_and_wait(
                topic=self._topic,
                key=order_id.encode(),
                value=json.dumps(event).encode()
            )
            logger.info(f"Published order.paid for order {order_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to publish order.paid: {e}")
            return False
