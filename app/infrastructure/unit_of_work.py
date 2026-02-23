from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.infrastructure.repositories import (
    SQLAlchemyOrderRepository,
    SQLAlchemyOutboxRepository,
    SQLAlchemyInboxRepository
)


class UnitOfWork:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]):
        self._session_factory = session_factory

    @asynccontextmanager
    async def __call__(self):
        async with self._session_factory() as session:
            try:
                # Создаем реализацию с репозиториями
                uow_impl = _UnitOfWorkImpl(session)
                yield uow_impl  # Отдаем внутреннюю реализацию
                # Если commit не вызван — rollback
                await session.rollback()
            except Exception:
                await session.rollback()
                raise


class _UnitOfWorkImpl:
    def __init__(self, session: AsyncSession):
        self._session = session
        self.orders = SQLAlchemyOrderRepository(session)
        self.outbox = SQLAlchemyOutboxRepository(session)
        self.inbox = SQLAlchemyInboxRepository(session)

    async def commit(self):
        await self._session.commit()

    async def rollback(self):
        await self._session.rollback()
