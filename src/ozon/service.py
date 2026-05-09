import httpx

from src.app.config import settings
from src.ozon.client import OzonClient
from src.ozon.models import OzonShop
from src.ozon.repository import OzonRepository


class OzonProductImportService:
    def __init__(self, repository: OzonRepository) -> None:
        self.repository = repository


    async def import_shop_products(self, shop: OzonShop) -> dict:
        async with httpx.AsyncClient(timeout=settings.autoalliance_timeout) as http_client:
            client = OzonClient(http_client=http_client, shop=shop)
            product_ids = await client.get_all_product_ids()
            items = await client.get_product_info_list_chunks(product_ids=product_ids)
        success = 0
        failed = 0
        for item in items:
            try:
                self.repository.upsert_product_from_ozon_item(shop=shop, item=item)
                self.repository.db.flush()
                success += 1
            except Exception as exc:
                self.repository.db.rollback()
                failed += 1

                print(
                    "FAILED:",
                    "offer_id=", item.get("offer_id"),
                    "product_id=", item.get("id") or item.get("product_id"),
                    "error=", repr(exc),
                )
        self.repository.db.commit()
        self.repository.add_sync_log(shop_id=shop.id, sync_type="ozon_products_import", 
                                     status="done" if failed == 0 else "partial", 
                                     message=f"Imported products for shop={shop.shop_name}", 
                                     items_total=len(product_ids), items_success=success, items_failed=failed)
        return {"shop": shop.shop_name, "total_ids": len(product_ids), "saved": success, "failed": failed}
