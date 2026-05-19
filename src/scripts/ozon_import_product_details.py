import argparse
import asyncio
import logging
import httpx
from pathlib import Path
from tqdm import tqdm

from src.app.logging_config import configure_logging
from src.app.db import SessionLocal, init_db
from src.ozon.client import OzonClient
from src.ozon.repository import OzonRepository


log = logging.getLogger(__name__)


def setup_logging() -> None:
    Path("data/logs").mkdir(parents=True, exist_ok=True)

    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(
                "data/logs/ozon_import_product_details.log",
                encoding="utf-8",
            ),
            logging.StreamHandler(),
        ],
    )


async def async_main() -> None:
    parser = argparse.ArgumentParser(
        description="Import Ozon product dimensions and weight"
    )
    parser.add_argument("--shop", default=None, help="Название магазина")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--only-empty", action="store_true")
    parser.add_argument("--batch-size", type=int, default=100)
    parser.add_argument("--delay", type=float, default=0.2)

    args = parser.parse_args()

    configure_logging("ozon_import_product_details")

    if args.batch_size > 100:
        raise RuntimeError("batch-size больше 100 не ставим")

    setup_logging()
    init_db()

    with SessionLocal() as db:
        repo = OzonRepository(db)

        shops = repo.list_shops()

        if args.shop:
            shops = [shop for shop in shops if shop.shop_name == args.shop]

        if not shops:
            raise RuntimeError("Магазины не найдены")

        all_stats = []

        for shop in shops:
            products = repo.list_products_for_details_import(
                shop_id=shop.id,
                only_empty=args.only_empty,
                limit=args.limit,
            )

            product_ids = [
                int(product.product_id)
                for product in products
                if product.product_id
            ]

            stats = {
                "shop": shop.shop_name,
                "total": len(product_ids),
                "saved": 0,
                "failed": 0,
            }

            if not product_ids:
                print(stats)
                all_stats.append(stats)
                continue

            headers = {
                "Client-Id": shop.client_id,
                "Api-Key": shop.token,
                "Content-Type": "application/json",
            }

            async with httpx.AsyncClient(
                base_url="https://api-seller.ozon.ru",
                headers=headers,
                timeout=60,
            ) as http_client:
                client = OzonClient(
                    http_client=http_client,
                    shop=shop,
                )

                batches = [
                    product_ids[i:i + args.batch_size]
                    for i in range(0, len(product_ids), args.batch_size)
                ]

                bar = tqdm(
                    batches,
                    desc=f"Ozon details: {shop.shop_name}",
                    unit="req",
                )

                for batch in bar:
                    try:
                        items = await client.get_product_attributes(
                            product_ids=batch,
                            limit=args.batch_size,
                        )

                        for item in items:
                            ok = repo.update_product_details_from_ozon_attributes(
                                item=item
                            )

                            if ok:
                                stats["saved"] += 1
                            else:
                                stats["failed"] += 1

                        db.commit()

                    except Exception as exc:
                        db.rollback()
                        stats["failed"] += len(batch)
                        log.exception(
                            "Ozon details failed shop=%s batch=%s error=%s",
                            shop.shop_name,
                            batch[:5],
                            exc,
                        )

                    bar.set_postfix(
                        saved=stats["saved"],
                        failed=stats["failed"],
                    )

                    await asyncio.sleep(args.delay)

            print(stats)
            all_stats.append(stats)

        print(all_stats)


if __name__ == "__main__":
    asyncio.run(async_main())