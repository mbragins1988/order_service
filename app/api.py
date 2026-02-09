from fastapi import APIRouter, HTTPException, status, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import os
import uuid
from app.kafka_service import KafkaService

from app.schemas import (
    CreateOrderRequest,
    OrderResponse,
    CatalogItem,
    ErrorResponse,
)
from app.models import OrderDB, OrderStatus
from app.database import get_db
from app.clients import CatalogClient, PaymentsClient
from app.outbox_service import OutboxService

API_TOKEN = os.getenv("API_TOKEN")
SERVICE_URL = os.getenv("SERVICE_URL")
router = APIRouter()
kafka_service = KafkaService()


@router.post(
    "/orders",
    response_model=OrderResponse,
    responses={400: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
    status_code=status.HTTP_201_CREATED,
)
async def create_order(
    order_request: CreateOrderRequest, db: AsyncSession = Depends(get_db)
):
    """Создать новый заказ."""
    print(
        f"Создание заказа для user: {order_request.user_id}, item: {order_request.item_id}"
    )
    # Проверка идемпотентности
    result = await db.execute(
        select(OrderDB).where(OrderDB.idempotency_key == order_request.idempotency_key)
    )
    existing_order = result.scalar_one_or_none()
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
            payment_id=existing_order.payment_id,
        )

    # Проверка товара в Catalog Service
    print(f"Проверка товара {order_request.item_id} в Catalog Service")
    catalog_data = await CatalogClient.get_item(order_request.item_id)

    if not catalog_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Товар не найден в Catalog Service",
        )

    catalog_item = CatalogItem(**catalog_data)

    # Проверка на доступность количества товара
    if catalog_item.available_qty < order_request.quantity:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Недостаточное количество товара. Доступно для заказа: {catalog_item.available_qty}",
        )

    print(
        f"Товар доступен: {catalog_item.name}, цена: {catalog_item.price}, в наличии: {catalog_item.available_qty}"
    )

    # Рассчитываем сумму заказа
    try:
        item_price = float(catalog_item.price)
        order_amount = str(item_price * order_request.quantity)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Некорректная цена товара",
        )

    # Создание заказа в БД
    order_id = str(uuid.uuid4())
    print(f"Создание заказа {order_id} в БД")

    order = OrderDB(
        id=order_id,
        user_id=order_request.user_id,
        quantity=order_request.quantity,
        item_id=order_request.item_id,
        status=OrderStatus.NEW,
        idempotency_key=order_request.idempotency_key,
        payment_id=None,
    )

    db.add(order)
    await db.commit()
    await db.refresh(order)

    # Создание платежа в Payments Service
    try:
        callback_url = f"{SERVICE_URL}/api/orders/payment-callback"
        print(f"Создание платежа для заказа {order_id}, callback_url: {callback_url}")
        payment_response = await PaymentsClient.create_payment(
            order_id=order_id,
            amount=order_amount,
            callback_url=callback_url,
            idempotency_key=f"payment_{order_request.idempotency_key}",
        )
        print(f"Платеж отправлен: {payment_response}")

        # Сохраняем payment_id в заказ
        order.payment_id = payment_response.get("id")
        await db.commit()
        await db.refresh(order)

    except Exception as e:
        print(f"Ошибка при создании платежа: {e}")

        # Откатываем транзакцию при ошибке
        await db.rollback()

    print(f"Заказ создан: {order_id}, ключ идемпотентности - {order.idempotency_key}")

    return OrderResponse(
        id=order.id,
        user_id=order.user_id,
        quantity=order.quantity,
        item_id=order.item_id,
        status=order.status,
        created_at=order.created_at,
        updated_at=order.updated_at,
        payment_id=order.payment_id,
    )


@router.get(
    "/orders/{order_id}",
    response_model=OrderResponse,
    responses={404: {"model": ErrorResponse}},
)
async def get_order(order_id: str, db: AsyncSession = Depends(get_db)):
    """Получить заказ по ID."""
    print(f"Поиск заказа: {order_id}")

    result = await db.execute(select(OrderDB).where(OrderDB.id == order_id))
    order = result.scalar_one_or_none()

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
        payment_id=order.payment_id,
    )


@router.post("/orders/payment-callback")
async def payment_callback(callback_data: dict, db: AsyncSession = Depends(get_db)):
    """Обработка callback от Payments Service"""
    print(f"Получен callback: {callback_data}")

    try:
        payment_id = callback_data.get("payment_id")
        order_id = callback_data.get("order_id")
        payment_status = callback_data.get("status")

        if not all([payment_id, order_id, payment_status]):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Некорректные данные в callback",
            )

        # Находим заказ
        result = await db.execute(select(OrderDB).where(OrderDB.id == order_id))
        order = result.scalar_one_or_none()

        if not order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Заказ не найден"
            )

        # Идемпотентность - если уже обработали
        if order.status == OrderStatus.PAID and payment_status == "succeeded":
            return {"status": "ok", "message": "Заказ уже обработан"}

        if order.status == OrderStatus.CANCELLED and payment_status == "failed":
            return {"status": "ok", "message": "Отменен"}

        # Обработка платежа
        if payment_status == "succeeded":
            order.status = OrderStatus.PAID

            outbox_service = OutboxService()
            event_data = {
                "order_id": order.id,
                "item_id": order.item_id,
                "quantity": str(order.quantity),
                "idempotency_key": f"order_paid_{order.id}_{uuid.uuid4()}",
            }
            print("event_data", event_data)
            # Сохраняем в outbox
            outbox_event = await outbox_service.save(
                db=db, event_type="order.paid", event_data=event_data, order_id=order.id
            )
            print(f"Событие {outbox_event.id} добавлено в outbox")

        elif payment_status == "failed":
            order.status = OrderStatus.CANCELLED
            print(f"Платеж не прошел для заказа {order_id}")

        if not order.payment_id:
            order.payment_id = payment_id

        await db.commit()

        return {"status": "ok", "message": "Callback обработан"}

    except HTTPException:
        raise
    except Exception as e:
        print(f"Ошибка обработки callback: {e}")

        # Откатываем транзакцию при ошибке
        try:
            await db.rollback()
        except:
            pass
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка обработки: {str(e)}",
        )
