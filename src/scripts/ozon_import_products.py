import argparse
import asyncio

from src.app.logging_config import configure_logging
from src.app.db import SessionLocal, init_db
from src.ozon.repository import OzonRepository
from src.ozon.service import OzonProductImportService


async def async_main() -> None:
    parser = argparse.ArgumentParser(description="Import Ozon products to local SQLite DB")
    parser.add_argument("--shop", default=None, help="Import only selected shop_name")
    args = parser.parse_args()

    configure_logging("ozon_import_products")
    init_db()
    with SessionLocal() as db:
        repo = OzonRepository(db)
        shops = [repo.get_shop_by_name(args.shop)] if args.shop else repo.list_active_shops()
        shops = [shop for shop in shops if shop is not None]
        if not shops:
            raise SystemExit("No shops found. Run: python -m src.scripts.ozon_add_shop")
        service = OzonProductImportService(repo)
        for shop in shops:
            print(await service.import_shop_products(shop))


if __name__ == "__main__":
    asyncio.run(async_main())
