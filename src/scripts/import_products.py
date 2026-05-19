import argparse
import asyncio
import logging
from pathlib import Path

from src.app.logging_config import configure_logging
from src.app.db import init_db
from src.autoalliance.parser.import_service import ImportProductsService


def setup_logging() -> None:
    Path("data/logs").mkdir(parents=True, exist_ok=True)

    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler("data/logs/autoalliance_import.log", encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )


async def async_main() -> None:
    parser = argparse.ArgumentParser(description="Import AutoAlliance products from table")
    parser.add_argument("file_path", help="Path to source xlsx/xls/csv file")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--batch-size", type=int, default=100)

    args = parser.parse_args()

    configure_logging("import_products")

    setup_logging()
    init_db()

    service = ImportProductsService(batch_size=args.batch_size)
    stats = await service.run(file_path=args.file_path, limit=args.limit)

    print("\n=== IMPORT DONE ===")
    print(stats)


if __name__ == "__main__":
    asyncio.run(async_main())
