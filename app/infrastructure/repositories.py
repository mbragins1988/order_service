import uuid
import json
from typing import Optional, List
from datetime import datetime, timezone
from sqlalchemy import select, insert, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models import Order, OrderStatus
from app.infrastructure.db_schema import orders_tbl, outbox_events_tbl, inbox_events_tbl
from app.application.interfaces import OrderRepository, OutboxRepository, InboxRepository


class SQLAlchemyOrderRepository(OrderRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_id(self, order_id: str) -> Optional[Order]:
        result = await self._session.execute(
            select(orders_tbl).where(orders_tbl.c.id == order_id)
        )
        row = result.fetchone()
        return self._to_domain(row) if row else None

    async def get_by_idempotency_key(self, key: str) -> Optional[Order]:
        result = await self._session.execute(
            select(orders_tbl).where(orders_tbl.c.idempotency_key == key)
        )
        row = result.fetchone()
        return self._to_domain(row) if row else None

    async def create(self, order: Order) -> None:
        stmt = insert(orders_tbl).values(
            id=order.id,
            user_id=order.user_id,
            quantity=order.quantity,
            item_id=order.item_id,
            status=order.status,
            idempotency_key=order.idempotency_key,
            payment_id=order.payment_id,
            created_at=order.created_at,
            updated_at=order.updated_at
        )
        await self._session.execute(stmt)

    async def update_status(self, order_id: str, status: OrderStatus) -> None:
        stmt = (
            update(orders_tbl)
            .where(orders_tbl.c.id == order_id)
            .values(
                status=status,
                updated_at=datetime.now(timezone.utc)
            )
        )
        await self._session.execute(stmt)

    async def update_payment_id(self, order_id: str, payment_id: str) -> None:
        stmt = (
            update(orders_tbl)
            .where(orders_tbl.c.id == order_id)
            .values(
                payment_id=payment_id,
                updated_at=datetime.now(timezone.utc)
            )
        )
        await self._session.execute(stmt)

    def _to_domain(self, row) -> Order:
        """Трансформация DB → Domain"""
        return Order(
            id=row.id,
            user_id=row.user_id,
            quantity=row.quantity,
            item_id=row.item_id,
            status=OrderStatus(row.status),
            idempotency_key=row.idempotency_key,
            payment_id=row.payment_id,
            created_at=row.created_at,
            updated_at=row.updated_at
        )


class SQLAlchemyOutboxRepository(OutboxRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def create(self, event_type: str, event_data: dict, order_id: str) -> str:
        event_id = str(uuid.uuid4())
        stmt = insert(outbox_events_tbl).values(
            id=event_id,
            event_type=event_type,
            event_data=event_data,  # SQLAlchemy JSON column сериализует автоматически
            order_id=order_id,
            status="pending"
        )
        await self._session.execute(stmt)
        return event_id

    async def get_pending(self, limit: int = 10) -> List[dict]:
        result = await self._session.execute(
            select(outbox_events_tbl)
            .where(outbox_events_tbl.c.status == "pending")
            .order_by(outbox_events_tbl.c.created_at.asc())
            .limit(limit)
        )
        rows = result.fetchall()

        return [
            {
                "id": row.id,
                "event_type": row.event_type,
                "event_data": row.event_data,
                "order_id": row.order_id
            }
            for row in rows
        ]

    async def mark_as_published(self, event_id: str) -> None:
        stmt = (
            update(outbox_events_tbl)
            .where(outbox_events_tbl.c.id == event_id)
            .values(status="published")
        )
        await self._session.execute(stmt)


class SQLAlchemyInboxRepository(InboxRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def create(self, event_type: str, event_data: dict, order_id: str, idempotency_key: str) -> str:
        event_id = str(uuid.uuid4())
        stmt = insert(inbox_events_tbl).values(
            id=event_id,
            event_type=event_type,
            event_data=event_data,
            order_id=order_id,
            idempotency_key=idempotency_key,
            status="pending"
        )
        await self._session.execute(stmt)
        return event_id

    async def get_pending(self, limit: int = 10) -> List[dict]:
        result = await self._session.execute(
            select(inbox_events_tbl)
            .where(inbox_events_tbl.c.status == "pending")
            .order_by(inbox_events_tbl.c.created_at.asc())
            .limit(limit)
        )
        rows = result.fetchall()

        return [
            {
                "id": row.id,
                "event_type": row.event_type,
                "event_data": row.event_data,
                "order_id": row.order_id,
                "idempotency_key": row.idempotency_key
            }
            for row in rows
        ]

    async def mark_as_processed(self, event_id: str) -> None:
        stmt = (
            update(inbox_events_tbl)
            .where(inbox_events_tbl.c.id == event_id)
            .values(
                status="processed",
                processed_at=datetime.now(timezone.utc)
            )
        )
        await self._session.execute(stmt)

    async def mark_as_failed(self, event_id: str) -> None:
        stmt = (
            update(inbox_events_tbl)
            .where(inbox_events_tbl.c.id == event_id)
            .values(status="failed")
        )
        await self._session.execute(stmt)

    async def is_processed(self, idempotency_key: str) -> bool:
        result = await self._session.execute(
            select(inbox_events_tbl)
            .where(
                inbox_events_tbl.c.idempotency_key == idempotency_key,
                inbox_events_tbl.c.status == "processed"
            )
        )
        return result.fetchone() is not None
