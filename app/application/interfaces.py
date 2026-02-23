from abc import ABC, abstractmethod
from typing import Optional, List
from app.domain.models import Order, Item


class OrderRepository(ABC):
    @abstractmethod
    async def get_by_id(self, order_id: str) -> Optional[Order]:
        pass

    @abstractmethod
    async def get_by_idempotency_key(self, key: str) -> Optional[Order]:
        pass

    @abstractmethod
    async def create(self, order: Order) -> None:
        pass

    @abstractmethod
    async def update_status(self, order_id: str, status) -> None:
        pass

    @abstractmethod
    async def update_payment_id(self, order_id: str, payment_id: str) -> None:
        pass


class OutboxRepository(ABC):
    @abstractmethod
    async def create(self, event_type: str, event_data: dict, order_id: str) -> str:
        pass

    @abstractmethod
    async def get_pending(self, limit: int = 10) -> List[dict]:
        pass

    @abstractmethod
    async def mark_as_published(self, event_id: str) -> None:
        pass


class InboxRepository(ABC):
    @abstractmethod
    async def create(self, event_type: str, event_data: dict, order_id: str, idempotency_key: str) -> str:
        pass

    @abstractmethod
    async def get_pending(self, limit: int = 10) -> List[dict]:
        pass

    @abstractmethod
    async def mark_as_processed(self, event_id: str) -> None:
        pass

    @abstractmethod
    async def mark_as_failed(self, event_id: str) -> None:
        pass

    @abstractmethod
    async def is_processed(self, idempotency_key: str) -> bool:
        pass


class UnitOfWork(ABC):
    @property
    @abstractmethod
    def orders(self) -> OrderRepository:
        pass

    @property
    @abstractmethod
    def outbox(self) -> OutboxRepository:
        pass

    @property
    @abstractmethod
    def inbox(self) -> InboxRepository:
        pass

    @abstractmethod
    async def __call__(self):
        pass

    @abstractmethod
    async def commit(self):
        pass

    @abstractmethod
    async def rollback(self):
        pass


class CatalogService(ABC):
    @abstractmethod
    async def get_item(self, item_id: str) -> Optional[Item]:
        pass


class PaymentsService(ABC):
    @abstractmethod
    async def create_payment(self, order_id: str, amount: str, callback_url: str, idempotency_key: str) -> dict:
        pass


class NotificationsService(ABC):
    @abstractmethod
    async def send(self, message: str, reference_id: str, idempotency_key: str, user_id: str) -> bool:
        pass

    @abstractmethod
    async def try_send(self, message: str, reference_id: str, idempotency_key: str, user_id: str) -> bool:
        pass


class KafkaProducer(ABC):
    @abstractmethod
    async def publish_order_paid(self, order_id: str, item_id: str, quantity: int, idempotency_key: str) -> bool:
        pass
