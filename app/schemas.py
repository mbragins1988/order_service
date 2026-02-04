from pydantic import BaseModel
from datetime import datetime
from typing import Optional
from app.models import OrderStatus


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
    payment_id: Optional[str] = None  # ← ДОБАВЛЯЕМ

    class Config:
        from_attributes = True


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


# Модель для callback от Payments Service
class PaymentCallbackRequest(BaseModel):
    payment_id: str
    order_id: str
    status: str  # "succeeded" или "failed"
    amount: str
    error_message: Optional[str] = None
