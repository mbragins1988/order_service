import httpx
import os
from typing import Dict, Any
from fastapi import HTTPException, status

CATALOG_BASE_URL = "https://capashino.dev-1.python-labs.ru"
API_TOKEN = os.getenv("API_TOKEN")

YOUR_SERVICE_URL = os.getenv("SERVICE_URL", "http://localhost:8000")


class CatalogClient:
    """Клиент для работы с Catalog Service"""

    @staticmethod
    async def get_item(item_id: str):
        """Получить товар из Catalog Service"""
        try:
            headers = {"X-API-Key": API_TOKEN}
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{CATALOG_BASE_URL}/api/catalog/items/{item_id}",
                    headers=headers,
                    timeout=10.0,
                )
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

                if response.status_code == 200:
                    return response.json()
                else:
                    raise Exception(
                        f"Payment service error: {response.status_code} - {response.text}"
                    )

        except Exception as e:
            raise Exception(f"Failed to create payment: {str(e)}")
