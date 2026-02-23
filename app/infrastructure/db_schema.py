from sqlalchemy import Table, Column, String, Integer, Enum, DateTime, JSON, MetaData
from sqlalchemy.sql import func
import enum

metadata = MetaData()


class OrderStatus(str, enum.Enum):
    NEW = "NEW"
    PAID = "PAID"
    SHIPPED = "SHIPPED"
    CANCELLED = "CANCELLED"


orders_tbl = Table(
    "orders",
    metadata,
    Column("id", String, primary_key=True),
    Column("user_id", String, nullable=False),
    Column("quantity", Integer, nullable=False),
    Column("item_id", String, nullable=False),
    Column("status", Enum(OrderStatus), default=OrderStatus.NEW),
    Column("idempotency_key", String, unique=True, index=True),
    Column("payment_id", String, nullable=True),
    Column("created_at", DateTime(timezone=True), server_default=func.now()),
    Column("updated_at", DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
)


outbox_events_tbl = Table(
    "outbox_events",
    metadata,
    Column("id", String, primary_key=True),
    Column("event_type", String, nullable=False),
    Column("event_data", JSON, nullable=False),
    Column("order_id", String, nullable=False),
    Column("status", String, default="pending"),
    Column("created_at", DateTime(timezone=True), server_default=func.now())
)


inbox_events_tbl = Table(
    "inbox_events",
    metadata,
    Column("id", String, primary_key=True),
    Column("event_type", String, nullable=False),
    Column("event_data", JSON, nullable=False),
    Column("order_id", String, nullable=False),
    Column("idempotency_key", String, unique=True, nullable=False),
    Column("status", String, default="pending"),
    Column("created_at", DateTime(timezone=True), server_default=func.now()),
    Column("processed_at", DateTime(timezone=True), nullable=True)
)


notifications_tbl = Table(
    "notifications",
    metadata,
    Column("id", String, primary_key=True),
    Column("user_id", String, nullable=False),
    Column("message", String, nullable=False),
    Column("reference_id", String, nullable=False),
    Column("idempotency_key", String, unique=True, index=True),
    Column("created_at", DateTime(timezone=True), server_default=func.now())
)
