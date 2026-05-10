import asyncio
import logging
from pathlib import Path

from src.app.db import init_db
from src.app.scheduler import create_scheduler, sync_postings_job


def setup_logging() -> None:
    Path("data/logs").mkdir(parents=True, exist_ok=True)

    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler("data/logs/worker.log", encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )


async def main() -> None:
    setup_logging()
    init_db()

    # Первый запуск сразу, не ждём 2 минуты.
    await sync_postings_job(days=7)

    scheduler = create_scheduler(
        interval_seconds=60,
        days=7,
    )

    scheduler.start()

    logging.info("Worker started. Posting sync interval: 60 seconds")

    try:
        while True:
            await asyncio.sleep(3600)
    except KeyboardInterrupt:
        logging.info("Worker stopped")


if __name__ == "__main__":
    asyncio.run(main())