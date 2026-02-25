from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.presentation.schemas import (
    CreateOrderRequest, OrderResponse, PaymentCallbackRequest, ErrorResponse
)
from app.application.create_order import CreateOrderUseCase, CreateOrderDTO
from app.application.get_order import GetOrderUseCase
from app.application.process_payment import ProcessPaymentCallbackUseCase, PaymentCallbackDTO
from app.domain.exceptions import (
    ItemNotFoundError, InsufficientStockError, OrderNotFoundError
)
from app.infrastructure.unit_of_work import UnitOfWork
from app.infrastructure.http_clients import (
    HTTPCatalogClient, HTTPPaymentsClient, HTTPNotificationsClient
)
from app.config import settings

router = APIRouter()


# Фабрики для создания use cases
def get_create_order_use_case(db: AsyncSession = Depends(get_db)):
    uow = UnitOfWork(lambda: db)
    catalog = HTTPCatalogClient(settings.CATALOG_BASE_URL, settings.API_TOKEN)
    payments = HTTPPaymentsClient(settings.CATALOG_BASE_URL, settings.API_TOKEN)
    notifications = HTTPNotificationsClient(settings.CATALOG_BASE_URL, settings.API_TOKEN)
    return CreateOrderUseCase(uow, catalog, payments, notifications, settings.SERVICE_URL)


def get_get_order_use_case(db: AsyncSession = Depends(get_db)):
    uow = UnitOfWork(lambda: db)
    return GetOrderUseCase(uow)


def get_process_payment_use_case(db: AsyncSession = Depends(get_db)):
    uow = UnitOfWork(lambda: db)
    return ProcessPaymentCallbackUseCase(uow)


@router.post(
    "/orders",
    response_model=OrderResponse,
    responses={400: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
    status_code=status.HTTP_201_CREATED
)
async def create_order(
    request: CreateOrderRequest,
    use_case: CreateOrderUseCase = Depends(get_create_order_use_case)
):
    """Создать новый заказ"""
    try:
        dto = CreateOrderDTO(
            user_id=request.user_id,
            quantity=request.quantity,
            item_id=request.item_id,
            idempotency_key=request.idempotency_key
        )
        order = await use_case(dto)
        return OrderResponse.from_domain(order)

    except ItemNotFoundError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except InsufficientStockError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Service unavailable: {str(e)}")


@router.get(
    "/orders/{order_id}",
    response_model=OrderResponse,
    responses={404: {"model": ErrorResponse}}
)
async def get_order(
    order_id: str,
    use_case: GetOrderUseCase = Depends(get_get_order_use_case)
):
    """Получить заказ по ID"""
    try:
        order = await use_case(order_id)
        return OrderResponse.from_domain(order)
    except OrderNotFoundError:
        raise HTTPException(status_code=404, detail="Заказ не найден")


@router.post("/orders/payment-callback")
async def payment_callback(
    callback: PaymentCallbackRequest,
    use_case: ProcessPaymentCallbackUseCase = Depends(get_process_payment_use_case)
):
    """Обработка callback от Payments Service"""
    try:
        dto = PaymentCallbackDTO(
            payment_id=callback.payment_id,
            order_id=callback.order_id,
            status=callback.status,
            amount=callback.amount,
            error_message=callback.error_message
        )
        await use_case(dto)
        return {"status": "ok", "message": "Callback обработан"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка обработки callback: {str(e)}")
