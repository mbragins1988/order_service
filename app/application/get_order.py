from app.domain.models import Order
from app.domain.exceptions import OrderNotFoundError


class GetOrderUseCase:
    def __init__(self, unit_of_work):
        self._uow = unit_of_work

    async def __call__(self, order_id: str) -> Order:
        async with self._uow() as uow:
            order = await uow.orders.get_by_id(order_id)
            if not order:
                raise OrderNotFoundError(f"Заказа {order_id} не найден")
            return order
