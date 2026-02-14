from app.base import Base
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
import os
from dotenv import load_dotenv


load_dotenv()

from app.models import OrderDB, OutboxEventDB, InboxEventDB, NotificationDB

engine = create_engine(os.getenv("POSTGRES_CONNECTION_STRING"))
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
def get_db_sync():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()