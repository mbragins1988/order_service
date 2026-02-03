from fastapi import FastAPI
from app.api import router
import uvicorn
from dotenv import load_dotenv

# Загружаем переменные окружения из .env файла
load_dotenv()

app = FastAPI(
    title="Order Service", description="Сервис для управления заказами", version="1.0.0"
)

# Подключаем роутер
app.include_router(router, prefix="/api")


# Корневой эндпоинт для проверки
@app.get("/")
async def root():
    return {"message": "Order Service is running"}


if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
