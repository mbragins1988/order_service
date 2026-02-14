from app.base import Base
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("POSTGRES_CONNECTION_STRING").replace("postgresql://", "postgresql+asyncpg://")
print('DATABASE_URL -', DATABASE_URL)
engine = create_async_engine(DATABASE_URL)

AsyncSessionLocal = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)



async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
