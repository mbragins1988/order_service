from fastapi import FastAPI
from app.api import router
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


app = FastAPI(
    title="Order Service",
    version="3.0.0",
)

app.include_router(router, prefix="/api")


@app.get("/")
async def root():
    return {"message": "Order Service запущен"}


@app.get("/health")
async def health():
    return {"status": "healthy", "kafka": "running"}
