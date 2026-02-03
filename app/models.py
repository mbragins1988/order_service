from sqlalchemy import Column, String, Integer, Enum, DateTime
from sqlalchemy.sql import func
import enum

# Импорт Base из database.py - ВАЖНО: только для наследования!
from app.database import Base


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
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
