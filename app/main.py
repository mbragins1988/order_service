from fastapi import FastAPI
from app.api import router
from app.database import engine
from app.models import Base
import uvicorn
from dotenv import load_dotenv

# Загружаем переменные окружения из .env файла
load_dotenv()

# Создание FastAPI приложения
app = FastAPI(
    title="Order Service",
    description="Сервис для управления заказами",
    version="1.0.0"
)

# Подключаем роутер
app.include_router(router, prefix="/api")

# Корневой эндпоинт для проверки
@app.get("/")
async def root():
    return {"message": "Order Service запущен"}
