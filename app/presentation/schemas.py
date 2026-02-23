from pydantic import BaseModel
from datetime import datetime
from typing import Optional

from app.domain.models import OrderStatus


class CreateOrderRequest(BaseModel):
    user_id: str
    quantity: int
    item_id: str
    idempotency_key: str


class OrderResponse(BaseModel):
    id: str
    user_id: str
    quantity: int
    item_id: str
    status: OrderStatus
    created_at: datetime
    updated_at: datetime
    payment_id: Optional[str] = None

    @classmethod
    def from_domain(cls, order):
        return cls(
            id=order.id,
            user_id=order.user_id,
            quantity=order.quantity,
            item_id=order.item_id,
            status=order.status,
            created_at=order.created_at,
            updated_at=order.updated_at,
            payment_id=order.payment_id
        )


class PaymentCallbackRequest(BaseModel):
    payment_id: str
    order_id: str
    status: str
    amount: str
    error_message: Optional[str] = None


class ErrorResponse(BaseModel):
    detail: str


class NotificationRequest(BaseModel):
    message: str
    reference_id: str
    idempotency_key: str
