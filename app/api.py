import asyncio
from fastapi import APIRouter, HTTPException, status, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import os
import sys
import uuid
import logging
from app.kafka_service import KafkaService

from app.schemas import (
    CreateOrderRequest,
    OrderResponse,
    NotificationRequest,
    NotificationResponse,
    CatalogItem,
    ErrorResponse
)
from app.models import OrderDB, OrderStatus, NotificationDB
from app.database import get_db
from app.clients import CatalogClient, PaymentsClient, NotificationsClient
from app.outbox_service import OutboxService


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

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
    logger.info(
        f"Создание заказа для user: {order_request.user_id}, item: {order_request.item_id}"
    )
    # Проверка идемпотентности
    result = await db.execute(
        select(OrderDB).where(OrderDB.idempotency_key == order_request.idempotency_key)
    )
    existing_order = result.scalar_one_or_none()
    if existing_order:
        logger.info(f"Найден существующий заказ: {existing_order.id}")
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
    logger.info(f"Проверка товара {order_request.item_id} в Catalog Service")
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

    logger.info(
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
    logger.info(f"Создание заказа {order_id} в БД")

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

    # Создаем уведомление
    notification_data = NotificationRequest(
        message="Ваш заказ создан и ожидает оплаты",
        reference_id=order_id,
        idempotency_key=f"notification_{order.idempotency_key}"
    )

    user_id = order.user_id
    max_retries = 5
    retry_count = 0
    notification_sent = False

    while not notification_sent and retry_count < max_retries:

        result = await notification(notification_data, user_id, db)
        logger.info(f"RESULT - {result}, Попытка {retry_count + 1}")
        if result:
            notification_sent = True
            logger.info(f"Уведомление о создании заказа отправлено (попытка {retry_count + 1})")
        else:
            retry_count += 1
            if retry_count < max_retries:
                logger.warning(f"Уведомление не отправилось {retry_count}")
                await asyncio.sleep(1)
            else:
                logger.error(f"Не удалось отправить уведомление после {max_retries} попыток")

    # Создание платежа в Payments Service
    try:
        callback_url = f"{SERVICE_URL}/api/orders/payment-callback"
        logger.info(f"Создание платежа для заказа {order_id}, callback_url: {callback_url}")
        payment_response = await PaymentsClient.create_payment(
            order_id=order_id,
            amount=order_amount,
            callback_url=callback_url,
            idempotency_key=f"payment_{order_request.idempotency_key}",
        )
        logger.info(f"Платеж отправлен: {payment_response}")

        # Сохраняем payment_id в заказ
        order.payment_id = payment_response.get("id")
        await db.commit()
        await db.refresh(order)

    except Exception as e:
        logger.info(f"Ошибка при создании платежа: {e}")

        # Откатываем транзакцию при ошибке
        await db.rollback()

    logger.info(f"Заказ создан: {order_id}, ключ идемпотентности - {order.idempotency_key}")

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
    logger.info(f"Поиск заказа: {order_id}")

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
    logger.info(f"Получен callback: {callback_data}")

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
        logger.info(f'payment_status: {payment_status}')
        # Идемпотентность - если уже обработали
        if order.status == OrderStatus.PAID and payment_status == "succeeded":
            return {"status": "ok", "message": "Заказ уже обработан"}

        if payment_status == "failed":
            return {"status": "ok", "message": "Заказ отменен"}

        # Обработка платежа
        if payment_status == "succeeded":
            order.status = OrderStatus.PAID
            # Отправляем в Outbox
            outbox_service = OutboxService()
            event_data = {
                "order_id": order.id,
                "item_id": order.item_id,
                "quantity": int(order.quantity),
                "idempotency_key": f"order_paid_{order.id}_{uuid.uuid4()}",
            }
            logger.info(f"event_data: {event_data}")
            # Сохраняем в outbox
            outbox_event = await outbox_service.save(
                db=db, event_type="order.paid", event_data=event_data, order_id=order.id
            )
            logger.info(f"Событие {outbox_event.id} добавлено в outbox")

        elif payment_status == "failed":
            order.status = OrderStatus.CANCELLED
            # Уведомление об отмене
            notification_data = NotificationRequest(
                message="Ваш заказ отменен. Причина: платеж не прошел",
                reference_id=order.id,
                idempotency_key=f"notification_cancelled_{order.id}_{uuid.uuid4()}"
            )
            await notification(notification_data, db, user_id=order.user_id)
            logger.info(f"Платеж не прошел для заказа {order_id}")

        if not order.payment_id:
            order.payment_id = payment_id

        await db.commit()

        return {"status": "ok", "message": "Callback обработан"}

    except Exception as e:
        logger.info(f"Ошибка обработки callback: {e}")

        # Откатываем транзакцию при ошибке
        try:
            await db.rollback()
        except:
            pass
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка обработки: {str(e)}",
        )


@router.post("/notifications")
async def notification(notifications: NotificationRequest,
                       user_id: str,
                       db: AsyncSession = Depends(get_db)):
    """Уведомление пользователю."""

    message = notifications.message
    reference_id = notifications.reference_id  # order-uuid
    idempotency_key = notifications.idempotency_key
    if not all([message, reference_id, idempotency_key]):
        return HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Некорректные данные",
        )
    # Проверка идемпотентности
    result = await db.execute(
        select(NotificationDB).where(NotificationDB.idempotency_key == idempotency_key)
    )
    existing_order = result.scalar_one_or_none()
    if existing_order:
        return HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Сообщение уже отправлялось",
        )
    note = NotificationDB(
        id=str(uuid.uuid4()),
        user_id=user_id,
        message=message,
        reference_id=reference_id,
        idempotency_key=idempotency_key
    )
    # Добавляем в сессию
    db.add(note)
    # Сохраняем в БД (commit)
    await db.commit()
    # Обновляем объект (получаем сгенерированные поля)
    await db.refresh(note)
    try:
        await NotificationsClient.send_notification(
            message=message,
            reference_id=reference_id,
            idempotency_key=idempotency_key
        )
        return NotificationResponse(
            id=note.id,
            user_id=note.user_id,
            message=note.message,
            reference_id=note.reference_id,
            created_at=note.created_at
        )
    except Exception as e:
        logger.info(f"Не удалось отправить уведомление в Capashino: {e}")
        # Продолжаем выполнение - уведомление сохранили в БД
        return False
