import argparse
import asyncio
import logging
from pathlib import Path

from src.app.logging_config import configure_logging
from src.app.db import SessionLocal, init_db
from src.ozon.sync.posting_sync_service import PostingSyncService


def setup_logging() -> None:
    Path("data/logs").mkdir(parents=True, exist_ok=True)

    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(
                "data/logs/ozon_sync_postings.log",
                encoding="utf-8",
            ),
            logging.StreamHandler(),
        ],
    )


async def async_main() -> None:
    parser = argparse.ArgumentParser(description="Sync Ozon FBS postings")
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--shop", default=None)

    args = parser.parse_args()

    configure_logging("ozon_sync_postings")

    setup_logging()
    init_db()

    with SessionLocal() as db:
        service = PostingSyncService(db)
        results = await service.sync_all_shops(
            days=args.days,
            shop_name=args.shop,
        )

    for result in results:
        print(result)


if __name__ == "__main__":
    asyncio.run(async_main())