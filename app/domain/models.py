from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel


class OrderStatus(str, Enum):
    NEW = "NEW"
    PAID = "PAID"
    SHIPPED = "SHIPPED"
    CANCELLED = "CANCELLED"


class Order(BaseModel):
    """Domain Entity — заказ"""
    id: str
    user_id: str
    quantity: int
    item_id: str
    status: OrderStatus
    idempotency_key: str
    payment_id: str | None = None
    created_at: datetime
    updated_at: datetime

    def can_be_paid(self) -> bool:
        """Бизнес-правило: можно оплатить только NEW заказ"""
        return self.status == OrderStatus.NEW

    def can_be_cancelled(self) -> bool:
        """Бизнес-правило: можно отменить только NEW или PAID"""
        return self.status in (OrderStatus.NEW, OrderStatus.PAID)

    def can_be_shipped(self) -> bool:
        """Бизнес-правило: можно отправить только PAID"""
        return self.status == OrderStatus.PAID


class Item(BaseModel):
    """Value Object — товар из каталога"""
    id: str
    name: str
    price: str
    available_qty: int
    created_at: datetime
