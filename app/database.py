from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.config import settings

# Асинхронный движок для приложения
async_engine = create_async_engine(settings.DATABASE_URL)
AsyncSessionLocal = async_sessionmaker(
    async_engine,           # Движок, который будет использовать
    class_=AsyncSession,    # Тип сессии (асинхронная)
    expire_on_commit=False  # Настройка: не устаревать после коммита
)


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
