import asyncio
import logging
from dataclasses import dataclass
import httpx
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from src.app.config import settings
from src.autoalliance.client import AutoAllianceClient
from src.autoalliance.models import AutoAlliancePurchase, SourceProduct
from src.ozon.models import OzonPosting, OzonPostingProduct


log = logging.getLogger(__name__)


@dataclass(slots=True)
class PurchaseStats:
    candidates: int = 0
    purchased: int = 0
    skipped: int = 0
    failed: int = 0

    def as_dict(self) -> dict:
        return {
            "candidates": self.candidates,
            "purchased": self.purchased,
            "skipped": self.skipped,
            "failed": self.failed,
        }


class AutoAlliancePurchaseService:
    def __init__(self, db: Session, *, delay: float = 0.2) -> None:
        self.db = db
        self.delay = delay


    async def purchase_new_postings(self) -> dict:
        stats = PurchaseStats()

        rows = self._list_items_for_purchase()
        stats.candidates = len(rows)

        headers = {
            "User-Agent": "autoalianse-worker",
        }

        if settings.autoalliance_api_key:
            headers["Authorization"] = f"Bearer {settings.autoalliance_api_key}"


        async with httpx.AsyncClient(
            base_url=settings.autoalliance_base_url,
            headers=headers,
            timeout=settings.autoalliance_timeout,
        ) as http_client:
            client = AutoAllianceClient(http_client)

            for posting, product, source_product in rows:
                qty = int(product.quantity or 1)

                for purchase_index in range(1, qty + 1):
                    purchase = self._get_or_create_purchase(
                        posting=posting,
                        product=product,
                        source_product=source_product,
                        purchase_index=purchase_index,
                    )

                    if purchase.status == "done":
                        stats.skipped += 1
                        continue

                    try:
                        purchase.status = "processing"
                        purchase.error_message = None
                        self.db.commit()

                        response = await client.create_order_from_items(
                            items=[
                                {
                                    "code": str(source_product.source_code),
                                    "quantity": 1,
                                }
                            ],
                            comment=(
                                f"Ozon {posting.posting_number}; "
                                f"offer_id={product.offer_id}; "
                                f"unit={purchase_index}"
                            ),
                        )

                        purchase.status = "done"
                        purchase.response_json = response
                        purchase.autoalliance_order_id = str(
                            response.get("orderId")
                            or response.get("order_id")
                            or response.get("id")
                            or ""
                        ) or None

                        self.db.commit()
                        stats.purchased += 1

                    except Exception as exc:
                        self.db.rollback()

                        purchase = self._get_or_create_purchase(
                            posting=posting,
                            product=product,
                            source_product=source_product,
                            purchase_index=purchase_index,
                        )

                        purchase.status = "failed"
                        purchase.error_message = str(exc)[:2000]
                        self.db.commit()

                        stats.failed += 1

                        log.exception(
                            "AutoAlliance purchase failed posting=%s offer_id=%s source_code=%s error=%s",
                            posting.posting_number,
                            product.offer_id,
                            source_product.source_code,
                            exc,
                        )

                    await asyncio.sleep(self.delay)

        return stats.as_dict()


    def _list_items_for_purchase(self):
        stmt = (
            select(OzonPosting, OzonPostingProduct, SourceProduct)
            .join(OzonPostingProduct, OzonPostingProduct.posting_id == OzonPosting.id)
            .join(
                SourceProduct,
                or_(
                    SourceProduct.article == OzonPostingProduct.offer_id,
                    SourceProduct.manufacturer_article == OzonPostingProduct.offer_id,
                    SourceProduct.factory_article == OzonPostingProduct.offer_id,
                ),
            )
            .where(
                OzonPosting.status == "awaiting_packaging",
                SourceProduct.source_code.is_not(None),
            )
            .order_by(OzonPosting.in_process_at.asc())
        )

        return self.db.execute(stmt).all()


    def _get_or_create_purchase(
        self,
        *,
        posting: OzonPosting,
        product: OzonPostingProduct,
        source_product: SourceProduct,
        purchase_index: int,
    ) -> AutoAlliancePurchase:
        purchase = self.db.scalar(
            select(AutoAlliancePurchase).where(
                AutoAlliancePurchase.posting_number == posting.posting_number,
                AutoAlliancePurchase.offer_id == product.offer_id,
                AutoAlliancePurchase.supplier_code == str(source_product.source_code),
                AutoAlliancePurchase.purchase_index == purchase_index,
            )
        )

        if purchase:
            return purchase

        purchase = AutoAlliancePurchase(
            shop_id=posting.shop_id,
            posting_number=posting.posting_number,
            offer_id=product.offer_id,
            sku=product.sku,
            supplier_code=str(source_product.source_code),
            purchase_index=purchase_index,
            quantity=1,
            status="new",
        )

        self.db.add(purchase)
        self.db.flush()

        return purchase