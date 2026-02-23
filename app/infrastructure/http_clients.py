import httpx
import logging
from typing import Optional

from app.domain.models import Item
from app.domain.exceptions import CatalogServiceError, PaymentServiceError

logger = logging.getLogger(__name__)


class HTTPCatalogClient:
    def __init__(self, base_url: str, api_token: str):
        self._base_url = base_url
        self._api_token = api_token

    async def get_item(self, item_id: str) -> Optional[Item]:
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self._base_url}/api/catalog/items/{item_id}",
                    headers={"X-API-Key": self._api_token},
                    timeout=10.0
                )

                if response.status_code == 200:
                    data = response.json()
                    return Item(**data)
                elif response.status_code == 404:
                    return None
                else:
                    raise CatalogServiceError(f"Catalog service error: {response.status_code}")

        except httpx.RequestError as e:
            logger.error(f"Catalog service connection error: {e}")
            raise CatalogServiceError(f"Catalog service unavailable: {str(e)}")


class HTTPPaymentsClient:
    def __init__(self, base_url: str, api_token: str):
        self._base_url = base_url
        self._api_token = api_token

    async def create_payment(self, order_id: str, amount: str, callback_url: str, idempotency_key: str) -> dict:
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self._base_url}/api/payments",
                    json={
                        "order_id": order_id,
                        "amount": amount,
                        "callback_url": callback_url,
                        "idempotency_key": idempotency_key
                    },
                    headers={
                        "X-API-Key": self._api_token,
                        "Content-Type": "application/json"
                    },
                    timeout=30.0
                )

                if response.status_code == 201:
                    return response.json()
                else:
                    raise PaymentServiceError(f"Payment service error: {response.status_code}")

        except httpx.RequestError as e:
            logger.error(f"Payment service connection error: {e}")
            raise PaymentServiceError(f"Payment service unavailable: {str(e)}")


class HTTPNotificationsClient:
    def __init__(self, base_url: str, api_token: str):
        self._base_url = base_url
        self._api_token = api_token

    async def send(self, message: str, reference_id: str, idempotency_key: str, user_id: str) -> bool:
        """Отправка уведомления (блокирующая)"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self._base_url}/api/notifications",
                    json={
                        "message": message,
                        "reference_id": reference_id,
                        "idempotency_key": idempotency_key
                    },
                    headers={"X-API-Key": self._api_token},
                    timeout=10.0
                )

                return response.status_code == 201

        except Exception as e:
            logger.error(f"Notification service error: {e}")
            return False

    async def try_send(self, message: str, reference_id: str, idempotency_key: str, user_id: str) -> bool:
        """Отправка уведомления (неблокирующая, с игнорированием ошибок)"""
        try:
            return await self.send(message, reference_id, idempotency_key, user_id)
        except Exception:
            return False
