import asyncio


class OrderRepository:
    async def create(self, order):
        return order


async def main():
    # Можно создать экземпляр
    repo = OrderRepository()
    result = await repo.create('jjj')
    print(result)

asyncio.run(main())