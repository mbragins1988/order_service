from fastapi import APIRouter, HTTPException, status, Depends
from sqlalchemy.orm import Session
import os
import uuid

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
    db.commit()
    db.refresh(order)

    # # Создание платежа в Payments Service
    try:
        callback_url = f"{SERVICE_URL}/api/orders/payment-callback"
        print(f"Создание платежа для заказа {order_id}, callback_url: {callback_url}")
        payment_response = await PaymentsClient.create_payment(
            order_id=order_id,
            amount=order_amount,
            callback_url=callback_url,
            idempotency_key=f"payment_{order_request.idempotency_key}",
        )
        print("Статус платежа", payment_response.get("status"))
        if payment_response.get("status") == "succeeded":
            order.status = OrderStatus.PAID  # ← ставим PAID сразу!
            order.payment_id = payment_response.get("id")
            print(f"Платеж выполнен, статус заказа: PAID")
        else:
            order.status = OrderStatus.CANCELLED
            print(f"Платеж не выполнен, статус заказа: CANCELLED")

        print(f"Платеж создан: {payment_response}")

        # Сохраняем payment_id в заказ
        order.payment_id = payment_response.get("id")
        db.commit()
        db.refresh(order)

    except Exception as e:
        print(f"Ошибка при создании платежа: {e}")

        # Если платеж не создан - отменяем заказ
        order.status = OrderStatus.CANCELLED  # ← Используем OrderStatus
        db.commit()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Не удалось выаолнить платеж: {str(e)}",
        )

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
async def get_order(order_id: str, db: Session = Depends(get_db)):
    """Получить заказ по ID."""
    print(f"Поиск заказа: {order_id}")

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
        payment_id=order.payment_id,
    )


@router.post("/orders/payment-callback")
async def payment_callback(callback_data: dict, db: Session = Depends(get_db)):
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
        order = db.query(OrderDB).filter(OrderDB.id == order_id).first()
        if not order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, 
                detail="Заказ не найден"
            )
        
        # Идемпотентность - если уже обработали
        if order.status == OrderStatus.PAID and payment_status == "succeeded":
            return {"status": "ok", "message": "Already processed"}
        
        if order.status == OrderStatus.CANCELLED and payment_status == "failed":
            return {"status": "ok", "message": "Already cancelled"}
        
        # Обработка платежа
        if payment_status == "succeeded":
            order.status = OrderStatus.PAID
            
            # Outbox + Kafka: публикуем событие order.paid
            outbox_service = OutboxService()
            
            event_data = {
                "order_id": order.id,
                "item_id": order.item_id,
                "quantity": str(order.quantity),
                "idempotency_key": f"order_paid_{order.id}_{uuid.uuid4()}"
            }
            
            outbox_event = outbox_service.save_and_publish(
                db=db,
                event_type="order.paid",
                event_data=event_data,
                order_id=order.id
            )
            
            print(f"Событие order.paid опубликовано: {outbox_event.id}")
            
        elif payment_status == "failed":
            order.status = OrderStatus.CANCELLED
            print(f"Платеж не прошел для заказа {order_id}")
        
        if not order.payment_id:
            order.payment_id = payment_id
        
        db.commit()
        
        return {"status": "ok", "message": "Callback processed"}
    
    except Exception as e:
        print(f"Ошибка обработки callback: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка обработки: {str(e)}",
        )
