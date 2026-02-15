from pydantic import BaseModel
from datetime import datetime
from typing import Optional
from app.models import OrderStatus


class CreateOrderRequest(BaseModel):
    """Создание заказа"""

    user_id: str
    quantity: int
    item_id: str
    idempotency_key: str


class OrderResponse(BaseModel):
    """Ответ с заказом"""

    id: str
    user_id: str
    quantity: int
    item_id: str
    status: OrderStatus
    created_at: datetime
    updated_at: datetime
    # payment_id: Optional[str] = None

    class Config:
        from_attributes = True


class CatalogItem(BaseModel):
    """Товары из Catalog Service"""

    id: str
    name: str
    price: str
    available_qty: int
    created_at: datetime


class ErrorResponse(BaseModel):

    detail: str


class PaymentCallbackRequest(BaseModel):
    """Callback от Payments Service"""

    payment_id: str
    order_id: str
    status: str  # "succeeded" или "failed"
    amount: str
    error_message: Optional[str] = None


# Kafka события
class OrderPaidEvent(BaseModel):
    event_type: str = "order.paid"
    order_id: str
    item_id: str
    quantity: int
    idempotency_key: str


class OrderShippedEvent(BaseModel):
    event_type: str = "order.shipped"
    order_id: str
    item_id: str
    quantity: int
    shipment_id: str


class OrderCancelledEvent(BaseModel):
    event_type: str = "order.cancelled"
    order_id: str
    item_id: str
    quantity: int
    reason: Optional[str] = None


class CreateOutboxEventRequest(BaseModel):
    """Сохранения в outbox"""

    event_type: str
    event_data: dict
    order_id: str


class NotificationRequest(BaseModel):
    message: str
    reference_id: str
    idempotency_key: str


class NotificationResponse(BaseModel):
    id: str
    user_id: str
    message: str
    reference_id: str
    created_at: datetime
