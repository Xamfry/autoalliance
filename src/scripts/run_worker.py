import asyncio
import logging

from src.app.db import init_db
from src.app.logging_config import configure_logging
from src.app.scheduler import (
    create_scheduler,
    sync_postings_job,
    sync_price_stock_job,
    purchase_new_postings_job,
)


# Интервал автосинхронизации цен и остатков: 3 часа.
PRICE_STOCK_SYNC_INTERVAL_SECONDS = 3 * 60 * 60



async def main() -> None:
    configure_logging("worker")
    init_db()

    # Первый запуск сразу, дальше по расписанию.
    await sync_postings_job(days=7)
    await sync_price_stock_job()
    await purchase_new_postings_job()

    scheduler = create_scheduler(
        interval_seconds=60,
        days=7,
        price_stock_interval_seconds=PRICE_STOCK_SYNC_INTERVAL_SECONDS,
    )

    scheduler.start()

    logging.info(
        "Worker started. Posting sync interval: 60 seconds. Price/stock sync interval: %s seconds",
        PRICE_STOCK_SYNC_INTERVAL_SECONDS,
    )

    try:
        while True:
            await asyncio.sleep(3600)
    except KeyboardInterrupt:
        logging.info("Worker stopped")


if __name__ == "__main__":
    asyncio.run(main())
