import argparse
import asyncio
import httpx
from sqlalchemy import select

from src.app.logging_config import configure_logging
from src.app.db import SessionLocal, init_db
from src.ozon.client import OzonClient
from src.ozon.models import OzonProduct
from src.ozon.repository import OzonRepository


def chunked(items: list, size: int) -> list[list]:
    return [items[i:i + size] for i in range(0, len(items), size)]


async def async_main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--shop_name", default=None)
    parser.add_argument("--yes", action="store_true")

    args = parser.parse_args()

    configure_logging("ozon_zero_stocks")

    init_db()

    with SessionLocal() as db:
        repo = OzonRepository(db)

        shops = repo.list_active_shops()

        if args.shop_name:
            shops = [s for s in shops if s.shop_name == args.shop_name]

        if not shops:
            raise RuntimeError("Магазины не найдены")

        print("Будут обнулены остатки:")

        for shop in shops:
            count = db.scalar(
                select(__import__("sqlalchemy").func.count(OzonProduct.id)).where(
                    OzonProduct.shop_id == shop.id,
                    OzonProduct.archived.is_(False),
                    OzonProduct.offer_id.is_not(None),
                )
            )
            print(f"- {shop.shop_name}: {count} товаров, warehouse={shop.warehouse}")

        if not args.yes:
            confirm = input("Введите ZERO для подтверждения: ").strip()

            if confirm != "ZERO":
                print("Отменено")
                return

        for shop in shops:
            if not shop.warehouse:
                print({"shop": shop.shop_name, "error": "warehouse не указан"})
                continue

            products = list(
                db.scalars(
                    select(OzonProduct).where(
                        OzonProduct.shop_id == shop.id,
                        OzonProduct.archived.is_(False),
                        OzonProduct.offer_id.is_not(None),
                    )
                )
            )

            async with httpx.AsyncClient(timeout=60) as http_client:
                client = OzonClient(http_client=http_client, shop=shop)

                total = 0

                for batch in chunked(products, 100):
                    payload = [
                        {
                            "offer_id": product.offer_id,
                            "stock": 0,
                            "warehouse_id": shop.warehouse,
                        }
                        for product in batch
                    ]

                    result = await client.update_stocks(payload)
                    total += len(payload)

                    print(
                        {
                            "shop": shop.shop_name,
                            "sent": len(payload),
                            "total": total,
                            "result": result,
                        }
                    )

            print({"shop": shop.shop_name, "zeroed": total})


if __name__ == "__main__":
    asyncio.run(async_main())
