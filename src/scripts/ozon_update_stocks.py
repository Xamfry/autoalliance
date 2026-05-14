import asyncio
import logging
from pathlib import Path

from src.app.db import SessionLocal, init_db
from src.ozon.sync.price_stock_sync_service import PriceStockSyncService


def setup_logging() -> None:
    Path("data/logs").mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler("data/logs/ozon_update_stocks.log", encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )


async def async_main() -> None:
    setup_logging()
    init_db()

    with SessionLocal() as db:
        service = PriceStockSyncService(db)
        results = await service.sync_all_shops()
        for result in results:
            print(result)


if __name__ == "__main__":
    asyncio.run(async_main())
