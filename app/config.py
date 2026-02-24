import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    # Database/
    POSTGRES_CONNECTION_STRING: str = os.getenv("POSTGRES_CONNECTION_STRING", "")

    # API
    API_TOKEN: str = os.getenv("API_TOKEN", "")
    SERVICE_URL: str = os.getenv("SERVICE_URL", "")

    # Services
    CATALOG_BASE_URL: str = os.getenv("CATALOG_BASE_URL", "https://capashino.dev-1.python-labs.ru")

    # Kafka
    KAFKA_BOOTSTRAP_SERVERS: str = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka.kafka.svc.cluster.local:9092")

    @property
    def DATABASE_URL(self) -> str:
        """Асинхронный URL для приложения"""
        return self.POSTGRES_CONNECTION_STRING.replace("postgres://", "postgresql+asyncpg://")

    @property
    def SYNC_DATABASE_URL(self) -> str:
        """Синхронный URL для Alembic"""
        return self.POSTGRES_CONNECTION_STRING.replace("postgres://", "postgresql://")


settings = Settings()
