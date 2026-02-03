from pydantic import BaseModel
from datetime import datetime
from enum import Enum


class OrderStatus(str, Enum):
    NEW = "NEW"
    PAID = "PAID"
    SHIPPED = "SHIPPED"
    CANCELLED = "CANCELLED"


# Модель для запроса на создание заказа
class CreateOrderRequest(BaseModel):
    user_id: str
    quantity: int
    item_id: str
    idempotency_key: str


# Модель для ответа с заказом
class OrderResponse(BaseModel):
    id: str
    user_id: str
    quantity: int
    item_id: str
    status: OrderStatus
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True  # Для совместимости с SQLAlchemy


# Модель для товара из Catalog Service
class CatalogItem(BaseModel):
    id: str
    name: str
    price: str
    available_qty: int
    created_at: datetime


# Модель для ошибки
class ErrorResponse(BaseModel):
    detail: str
