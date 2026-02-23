import json
import logging
import asyncio
from aiokafka import AIOKafkaConsumer

logger = logging.getLogger(__name__)


class KafkaConsumerClient:
    def __init__(self, bootstrap_servers: str, group_id: str = "order-service-group"):
        self._bootstrap_servers = bootstrap_servers
        self._group_id = group_id
        self._topic = "student_system-shipment.events"
        self._consumer: AIOKafkaConsumer | None = None

    async def start(self):
        self._consumer = AIOKafkaConsumer(
            self._topic,
            bootstrap_servers=self._bootstrap_servers,
            group_id=self._group_id,
            value_deserializer=lambda v: json.loads(v.decode())
        )
        await self._consumer.start()
        logger.info("Kafka consumer started")

    async def stop(self):
        if self._consumer:
            await self._consumer.stop()
            self._consumer = None
            logger.info("Kafka consumer stopped")

    async def consume(self, callback):
        """Бесконечный цикл потребления сообщений"""
        try:
            async for msg in self._consumer:
                try:
                    event_data = msg.value
                    logger.info(f"Received event: {event_data.get('event_type')}")
                    await callback(event_data)
                    await self._consumer.commit()
                except Exception as e:
                    logger.error(f"Error processing message: {e}")
                    await asyncio.sleep(1)

        except Exception as e:
            logger.error(f"Consumer error: {e}")
