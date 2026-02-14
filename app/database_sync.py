from app.base import Base
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
import os
from dotenv import load_dotenv


load_dotenv()

from app.models import OrderDB, OutboxEventDB, InboxEventDB, NotificationDB
DATABASE_URL = os.getenv("POSTGRES_CONNECTION_STRING").replace("postgres://", "postgresql://")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
def get_db_sync():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()