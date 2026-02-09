import json
import uuid
from app.models import OutboxEventDB


class OutboxService:
    @staticmethod
    async def save(db, event_type: str, event_data: dict, order_id: str):
        """Сохраняем в outbox"""
        outbox_event = OutboxEventDB(
            id=str(uuid.uuid4()),
            event_type=event_type,
            event_data=json.dumps(event_data),
            order_id=order_id,
            status="pending",
        )
        db.add(outbox_event)
        return outbox_event
