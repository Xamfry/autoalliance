import argparse
import asyncio
import logging
import httpx
from pathlib import Path
from sqlalchemy import select
from tqdm import tqdm

from src.app.db import SessionLocal, init_db
from src.autoalliance.client import AutoAllianceClient
from src.autoalliance.models import AutoAllianceProduct
from src.autoalliance.repository import AutoAllianceRepository


log = logging.getLogger(__name__)


async def async_main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--delay", type=float, default=0.2)
    parser.add_argument("--only-empty", action="store_true")
    args = parser.parse_args()

    init_db()

    with SessionLocal() as db:
        query = select(AutoAllianceProduct).where(
            AutoAllianceProduct.parse_status == "found",
            AutoAllianceProduct.supplier_code.is_not(None),
        )

        if args.only_empty:
            query = query.where(AutoAllianceProduct.preview_applicabilities_json.is_(None))

        if args.limit:
            query = query.limit(args.limit)

        products = list(db.scalars(query))

        async with httpx.AsyncClient(timeout=60) as http_client:
            client = AutoAllianceClient(http_client)
            repo = AutoAllianceRepository(db)

            ok = 0
            failed = 0

            for product in tqdm(products, desc="Preview import", unit="product"):
                try:
                    print(f"\nImporting preview for supplier_code={product.supplier_code}")
                    preview = await client.get_product_preview(product.supplier_code)

                    if preview:
                        repo.update_product_preview_from_json(
                            product=product,
                            preview=preview,
                        )
                        ok += 1
                    else:
                        failed += 1

                    db.commit()

                except Exception as exc:
                    failed += 1
                    db.rollback()
                    print(f"FAILED supplier_code={product.supplier_code}: {exc}")
                    log.exception("Preview failed supplier_code=%s: %s", product.supplier_code, exc)

                await asyncio.sleep(args.delay)

    print({"total": len(products), "ok": ok, "failed": failed})


if __name__ == "__main__":
    asyncio.run(async_main())