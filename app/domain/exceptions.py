class DomainException(Exception):
    pass


class CatalogServiceError(DomainException):
    pass


class PaymentServiceError(DomainException):
    pass


class ItemNotFoundError(DomainException):
    pass


class InsufficientStockError(DomainException):
    def __init__(self, available: int, required: int):
        self.available = available
        self.required = required
        super().__init__(f"Недостаточно товара. Доступно: {available}, требуется: {required}")


class OrderNotFoundError(DomainException):
    pass
