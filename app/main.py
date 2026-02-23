from fastapi import FastAPI
from app.presentation.api import router

app = FastAPI(title="Order Service")
app.include_router(router, prefix="/api")


@app.get("/")
async def root():
    return {
        "service": "Order Service",
        "status": "running",
    }


@app.get("/health")
async def health():
    return {"status": "healthy"}
