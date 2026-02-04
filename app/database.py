from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv

# Загружаем .env
# load_dotenv()

print("=== DATABASE CONFIG DEBUG ===")
print(f"POSTGRES_USERNAME: {os.getenv('POSTGRES_USERNAME')}")
print(f"POSTGRES_PASSWORD: {'*' * 8 if os.getenv('POSTGRES_PASSWORD') else 'NOT SET'}")
print(f"POSTGRES_HOST: {os.getenv('POSTGRES_HOST')}")
print(f"POSTGRES_PORT: {os.getenv('POSTGRES_PORT')}")
print(f"POSTGRES_DATABASE_NAME: {os.getenv('POSTGRES_DATABASE_NAME')}")
print(f"POSTGRES_CONNECTION_STRING: {os.getenv('POSTGRES_CONNECTION_STRING')}")
print(f"DATABASE_URL from env: {os.getenv('DATABASE_URL')}")

# Получаем URL из .env
DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
