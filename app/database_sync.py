from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
import os
from dotenv import load_dotenv

load_dotenv()

engine = create_engine(os.getenv("POSTGRES_CONNECTION_STRING"))
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db_sync():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()