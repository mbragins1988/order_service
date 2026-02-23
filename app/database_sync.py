from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.config import settings

# Синхронный движок для Alembic и скриптов
sync_engine = create_engine(settings.SYNC_DATABASE_URL)
SyncSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=sync_engine)


def get_sync_db():
    db = SyncSessionLocal()
    try:
        yield db
    finally:
        db.close()
