from sqlalchemy import Column, String, Integer, Enum, DateTime, JSON
from sqlalchemy.sql import func
import enum

from app.database_sync import Base


class OrderStatus(str, enum.Enum):
    NEW = "NEW"
    PAID = "PAID"
    SHIPPED = "SHIPPED"
    CANCELLED = "CANCELLED"


# SQLAlchemy модель для БД
class OrderDB(Base):
    __tablename__ = "orders"

    id = Column(String, primary_key=True, index=True)
    user_id = Column(String, nullable=False)
    quantity = Column(Integer, nullable=False)
    item_id = Column(String, nullable=False)
    status = Column(Enum(OrderStatus), default=OrderStatus.NEW)
    idempotency_key = Column(String, unique=True, index=True)
    payment_id = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class OutboxEventDB(Base):
    """Таблица для исходящих событий"""

    __tablename__ = "outbox_events"

    id = Column(String, primary_key=True)
    event_type = Column(String, nullable=False)
    event_data = Column(JSON, nullable=False)  # Используем JSON тип
    order_id = Column(String, nullable=False)
    status = Column(String, default="pending")  # pending, published, failed
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class InboxEventDB(Base):
    """Таблица для входящих событий (для идемпотентности)"""

    __tablename__ = "inbox_events"

    id = Column(String, primary_key=True)
    event_type = Column(String, nullable=False)
    event_data = Column(JSON, nullable=False)
    order_id = Column(String, nullable=False)
    idempotency_key = Column(String, unique=True, nullable=False)
    status = Column(String, default="pending")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    processed_at = Column(DateTime(timezone=True), nullable=True)


class NotificationDB(Base):
    """Уведомление пользователю."""

    __tablename__ = "notifications"

    id = Column(String, primary_key=True)
    user_id = Column(String, nullable=False)
    message = Column(String, nullable=False)
    reference_id = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    idempotency_key = Column(String, unique=True, index=True)
