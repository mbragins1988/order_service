import httpx
import logging
from typing import Optional
import asyncio

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
                    raise CatalogServiceError(f"Catalog service ошибка: {response.status_code}")

        except httpx.RequestError as e:
            logger.error(f"Catalog service ошибка подключения: {e}")
            raise CatalogServiceError(f"Catalog service не доступен: {str(e)}")


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
                    raise PaymentServiceError(f"Payment service ошибка: {response.status_code}")

        except httpx.RequestError as e:
            logger.error(f"Payment service ошибка подключения: {e}")
            raise PaymentServiceError(f"Payment service не доступен: {str(e)}")


class HTTPNotificationsClient:
    def __init__(self, base_url: str, api_token: str, max_retries: int = 10, retry_delay: float = 1.0):
        self._base_url = base_url
        self._api_token = api_token
        self._max_retries = max_retries
        self._retry_delay = retry_delay

    async def send(self, message: str, reference_id: str, idempotency_key: str, user_id: str) -> bool:
        """Отправка уведомления с повторными попытками"""
        for attempt in range(self._max_retries):
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
                    
                    if response.status_code == 201:
                        logger.info(f"Уведомление отправлено (попытка {attempt + 1})")
                        return True
                    else:
                        logger.warning(f"Уведомление вернуло статус {response.status_code}")
                        
            except Exception as e:
                logger.warning(f"Ошибка отправки уведомления (попытка {attempt + 1}/{self._max_retries}): {e}")
            
            # Ждем перед следующей попыткой (кроме последней)
            if attempt < self._max_retries - 1:
                await asyncio.sleep(self._retry_delay)
        
        logger.error(f"Не удалось отправить уведомление после {self._max_retries} попыток")
        return False
