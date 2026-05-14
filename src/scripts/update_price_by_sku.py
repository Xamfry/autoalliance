import argparse
import asyncio
import httpx

from src.app.db import SessionLocal, init_db
from src.ozon.client import OzonClient
from src.ozon.repository import OzonRepository


async def async_main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--article", required=True)
    parser.add_argument("--price", required=True, type=float)
    parser.add_argument("--shop_name", default=None)

    args = parser.parse_args()

    init_db()

    with SessionLocal() as db:
        repo = OzonRepository(db)

        shops = repo.list_active_shops()

        if args.shop_name:
            shops = [s for s in shops if s.shop_name == args.shop_name]

        if not shops:
            raise RuntimeError("Магазины не найдены")

        for shop in shops:
            product = db.scalar(
                __import__("sqlalchemy").select(
                    __import__("src.ozon.models", fromlist=["OzonProduct"]).OzonProduct
                ).where(
                    __import__("src.ozon.models", fromlist=["OzonProduct"]).OzonProduct.shop_id == shop.id,
                    __import__("src.ozon.models", fromlist=["OzonProduct"]).OzonProduct.offer_id == args.article,
                )
            )

            if not product:
                print({"shop": shop.shop_name, "article": args.article, "status": "not_found"})
                continue

            async with httpx.AsyncClient(timeout=60) as http_client:
                client = OzonClient(http_client=http_client, shop=shop)

                payload = [
                    {
                        "offer_id": product.offer_id,
                        "price": str(int(args.price)),
                        "old_price": str(int(args.price * 1.2)),
                    }
                ]

                result = await client.update_prices(payload)

                product.price_calc = int(args.price)
                db.commit()

                print(
                    {
                        "shop": shop.shop_name,
                        "article": product.offer_id,
                        "price": int(args.price),
                        "result": result,
                    }
                )


if __name__ == "__main__":
    asyncio.run(async_main())