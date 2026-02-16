import httpx
import os
import sys
from typing import Dict, Any
from fastapi import HTTPException, status
import logging


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

CATALOG_BASE_URL = os.getenv("CATALOG_BASE_URL")
API_TOKEN = os.getenv("API_TOKEN")


class CatalogClient:
    """Клиент для работы с Catalog Service"""

    @staticmethod
    async def get_item(item_id: str):
        """Получить товар из Catalog Service"""
        try:
            headers = {"X-API-Key": API_TOKEN}
            async with httpx.AsyncClient() as client:
                logger.info(f"URL: {CATALOG_BASE_URL}/api/catalog/items/{item_id}")
                response = await client.get(
                    f"{CATALOG_BASE_URL}/api/catalog/items/{item_id}",
                    headers=headers,
                    timeout=10.0,
                )
                logger.info(f"RESPONSE: {response}")
                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 404:
                    return None
                else:
                    raise HTTPException(
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        detail="Catalog Service недоступен",
                    )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Ошибка соединения с Catalog Service: {str(e)}",
            )


class PaymentsClient:
    """Клиент для работы с Payments Service"""

    @staticmethod
    async def create_payment(
        order_id: str, amount: str, callback_url: str, idempotency_key: str
    ) -> Dict[str, Any]:
        """Создать платеж в Payments Service"""
        try:
            headers = {"X-API-Key": API_TOKEN, "Content-Type": "application/json"}
            payload = {
                "order_id": order_id,
                "amount": amount,
                "callback_url": callback_url,
                "idempotency_key": idempotency_key,
            }
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{CATALOG_BASE_URL}/api/payments",
                    json=payload,
                    headers=headers,
                    timeout=30.0,
                )
                logger.info(f"RESPONSE: {response}, payload: {payload}")

                if response.status_code == 201:
                    return response.json()
                else:
                    raise Exception(
                        f"Ошибка Payment service: {response.status_code} - {response.text}"
                    )

        except Exception as e:
            raise Exception(f"Не удалось выполнить платеж: {str(e)}")


class NotificationsClient:
    """Клиент для работы с Notifications Service"""
    
    @staticmethod
    async def send_notification(
        message: str,
        reference_id: str,
        idempotency_key: str
    ) -> dict:
        """Отправить уведомление в Notifications Service"""
        try:
            headers = {
                "X-API-Key": API_TOKEN,
                "Content-Type": "application/json"
            }
            payload = {
                "message": message,
                "reference_id": reference_id,
                "idempotency_key": idempotency_key
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{CATALOG_BASE_URL}/api/notifications",
                    json=payload,
                    headers=headers,
                    timeout=10.0
                )
                
                if response.status_code == 201:
                    return response.json()
                else:
                    logger.info(f"Ошибка Notifications Service: {response.status_code}")
                    # Генерируем исключение!
                    raise Exception(f"Notifications Service вернул {response.status_code}")
                    
        except Exception as e:
            logger.info(f"Ошибка отправки уведомления: {e}")
            raise
