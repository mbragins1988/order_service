import logging
from pydantic import BaseModel
from datetime import datetime
import uuid

from app.domain.models import Order, OrderStatus, Item
from app.domain.exceptions import ItemNotFoundError, InsufficientStockError
from app.application.interfaces import UnitOfWork, CatalogService, PaymentsService, NotificationsService


logger = logging.getLogger(__name__)


class CreateOrderDTO(BaseModel):
    user_id: str
    quantity: int
    item_id: str
    idempotency_key: str


class CreateOrderUseCase:
    def __init__(
        self,
        unit_of_work,
        catalog_service: CatalogService,
        payments_service: PaymentsService,
        notifications_service: NotificationsService,
        service_url: str
    ):
        self._uow = unit_of_work
        self._catalog = catalog_service
        self._payments = payments_service
        self._notifications = notifications_service
        self._service_url = service_url

    async def __call__(self, order_data: CreateOrderDTO) -> Order:
        logger.info(f"Создание заказа для пользователя {order_data.user_id}, item {order_data.item_id}")

        # 1. Проверка идемпотентности
        async with self._uow() as uow:
            existing = await uow.orders.get_by_idempotency_key(order_data.idempotency_key)
            if existing:
                logger.info(f"Заказ уже существует: {existing.id}")
                return existing

        # 2. Проверка каталога
        item = await self._catalog.get_item(order_data.item_id)
        if not item:
            raise ItemNotFoundError(f"Товар {order_data.item_id} не найден")
        if item.available_qty < order_data.quantity:
            raise InsufficientStockError(item.available_qty, order_data.quantity)
        # 3. Расчет суммы
        amount = float(item.price) * order_data.quantity
        # 4. Создание заказа
        now = datetime.now()
        order = Order(
            id=str(uuid.uuid4()),
            user_id=order_data.user_id,
            quantity=order_data.quantity,
            item_id=order_data.item_id,
            status=OrderStatus.NEW,
            idempotency_key=order_data.idempotency_key,
            created_at=now,
            updated_at=now
        )
        await uow.orders.create(order)
        await uow.commit()
        logger.info(f"Заказ создан: {order.id}")

        # Уведомление
        notifications = await self._notifications.send(
            message="Ваш заказ создан (NEW) и ожидает оплаты",
            reference_id=order.id,
            idempotency_key=f"notification_created_{order.idempotency_key}",
            user_id=order.user_id
        )
        if notifications:
            logger.info(f"Отправлено уведомление 'Ваш заказ создан (NEW) и ожидает оплаты' для {order.id}")
        else:
            logger.info(f"Не отправлено уведомление 'Ваш заказ создан (NEW) и ожидает оплаты' для {order.id}")
        print(notifications)
        # Создание платежа
        try:
            callback_url = f"{self._service_url}/api/orders/payment-callback"
            payment = await self._payments.create_payment(
                order_id=order.id,
                amount=str(amount),
                callback_url=callback_url,
                idempotency_key=f"payment_{order_data.idempotency_key}"
            )

            # Обновляем payment_id в заказе
            async with self._uow() as uow:
                await uow.orders.update_payment_id(order.id, payment["id"])
                await uow.commit()

        except Exception as e:
            logger.error(f"Ошибка создания заказа: {e}")
            # Не блокируем создание заказа

        return order
