import asyncio
import logging
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.database import AsyncSessionLocal
from app.infrastructure.unit_of_work import UnitOfWork
from app.infrastructure.http_clients import HTTPNotificationsClient
from app.application.process_inbox import ProcessInboxEventsUseCase
from app.config import settings

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

notifications_client = HTTPNotificationsClient(settings.CATALOG_BASE_URL, settings.API_TOKEN)


async def inbox_worker():
    """Worker для обработки inbox событий"""
    logger.info("Inbox worker запущен")

    while True:
        try:
            # создаем UoW с фабрикой сессий
            uow = UnitOfWork(AsyncSessionLocal)
            
            use_case = ProcessInboxEventsUseCase(
                unit_of_work=uow,
                notifications_client=notifications_client
            )
            
            processed = await use_case(limit=10)
            if processed:
                logger.info(f"Обработка {processed} inbox events")
                
            await asyncio.sleep(2)
            
        except Exception as e:
            logger.error(f"Ошибка в  inbox worker: {e}", exc_info=True)
            await asyncio.sleep(10)


async def main():
    await inbox_worker()


if __name__ == "__main__":
    asyncio.run(main())
