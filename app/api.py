from fastapi import APIRouter, HTTPException, status, Depends
from sqlalchemy.orm import Session
import os
import httpx
import uuid


from app.schemas import (
    CreateOrderRequest,
    OrderResponse,
    CatalogItem,
    ErrorResponse,
    OrderStatus,
)
from app.models import OrderDB
from app.database import get_db

router = APIRouter()

# Глобальные настройки
CATALOG_BASE_URL = "https://capashi.dev-1.python-labs.ru"
API_TOKEN = os.getenv("API_TOKEN")


async def get_catalog_item(item_id: str) -> CatalogItem:
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
                print("Товар выбран")
                return CatalogItem(**response.json())
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


@router.post(
    "/orders",
    response_model=OrderResponse,
    responses={400: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
    status_code=status.HTTP_201_CREATED,
)
async def create_order(
    order_request: CreateOrderRequest, db: Session = Depends(get_db)
):
    """Создать новый заказ."""
    print(
        f"Создание заказа для user: {order_request.user_id}, item: {order_request.item_id}"
    )

    # Проверка идемпотентности
    existing_order = (
        db.query(OrderDB)
        .filter(OrderDB.idempotency_key == order_request.idempotency_key)
        .first()
    )

    if existing_order:
        print(f"Найден существующий заказ: {existing_order.id}")
        return OrderResponse(
            id=existing_order.id,
            user_id=existing_order.user_id,
            quantity=existing_order.quantity,
            item_id=existing_order.item_id,
            status=existing_order.status,
            created_at=existing_order.created_at,
            updated_at=existing_order.updated_at,
        )

    # Проверка товара в Catalog Service
    print(f"Проверка товара {order_request.item_id} в Catalog Service")
    catalog_item = await get_catalog_item(order_request.item_id)

    if not catalog_item:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Товар не найден в Catalog Service",
        )
    # Проверка на доступность количества товара
    if catalog_item.available_qty < order_request.quantity:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Недостаточное количество товара. Доступно для заказа: {catalog_item.available_qty}",
        )

    print(
        f"Товар доступен: {catalog_item.name}, цена: {catalog_item.price}, в наличии: {catalog_item.available_qty}"
    )

    # Создание заказа в БД
    order_id = str(uuid.uuid4())
    print(f"Сохранение заказа {order_id} в БД")

    order = OrderDB(
        id=order_id,
        user_id=order_request.user_id,
        quantity=order_request.quantity,
        item_id=order_request.item_id,
        status=OrderStatus.NEW.value,
        idempotency_key=str(uuid.uuid4()),  # Генерируем ключ идемпотентности
    )

    db.add(order)
    db.commit()
    db.refresh(order)

    print(f"Заказ создан: {order_id}, ключ идемпотентности - {order.idempotency_key}")

    # 4. Возврат результата
    return OrderResponse(
        id=order.id,
        user_id=order.user_id,
        quantity=order.quantity,
        item_id=order.item_id,
        status=order.status,
        created_at=order.created_at,
        updated_at=order.updated_at,
    )


@router.get(
    "/orders/{order_id}",
    response_model=OrderResponse,
    responses={404: {"model": ErrorResponse}},
)
async def get_order(order_id: str, db: Session = Depends(get_db)):
    """Получить заказ по ID."""
    print(f"🔍 Поиск заказа: {order_id}")

    order = db.query(OrderDB).filter(OrderDB.id == order_id).first()

    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Заказ не найден"
        )

    return OrderResponse(
        id=order.id,
        user_id=order.user_id,
        quantity=order.quantity,
        item_id=order.item_id,
        status=order.status,
        created_at=order.created_at,
        updated_at=order.updated_at,
    )
