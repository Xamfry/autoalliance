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
    no_match: int = 0
    failed: int = 0

    def as_dict(self) -> dict:
        return {
            "candidates": self.candidates,
            "purchased": self.purchased,
            "skipped": self.skipped,
            "no_match": self.no_match,
            "failed": self.failed,
        }


class AutoAlliancePurchaseService:
    def __init__(self, db: Session, *, delay: float = 0.2) -> None:
        self.db = db
        self.delay = delay

    async def purchase_new_postings(self) -> dict:
        stats = PurchaseStats()

        rows = self._list_posting_products()
        stats.candidates = len(rows)
        log.info("AutoAlliance purchase candidates: %s", stats.candidates)

        headers = {"User-Agent": "autoalianse-worker"}

        if settings.autoalliance_api_key:
            headers["Authorization"] = f"Bearer {settings.autoalliance_api_key}"

        async with httpx.AsyncClient(
            base_url=settings.autoalliance_base_url,
            headers=headers,
            timeout=settings.autoalliance_timeout,
        ) as http_client:
            client = AutoAllianceClient(http_client)

            for posting, product in rows:
                log.info(
                    "AutoAlliance purchase candidate: posting=%s offer_id=%s sku=%s qty=%s",
                    posting.posting_number,
                    product.offer_id,
                    product.sku,
                    product.quantity,
                )
                source_product = self._find_source_product(product)

                if not source_product or not source_product.source_code:
                    stats.no_match += 1
                    log.warning(
                        "AutoAlliance purchase skipped: source product not found posting=%s offer_id=%s",
                        posting.posting_number,
                        product.offer_id,
                    )
                    continue

                qty = max(1, int(product.quantity or 1))

                for purchase_index in range(1, qty + 1):
                    purchase = self._get_or_create_purchase(
                        posting=posting,
                        product=product,
                        source_product=source_product,
                        purchase_index=purchase_index,
                    )

                    if purchase.status in {"done", "processing", "failed"}:
                        stats.skipped += 1
                        log.info(
                            "AutoAlliance purchase skipped: posting=%s offer_id=%s source_code=%s unit=%s status=%s",
                            posting.posting_number,
                            product.offer_id,
                            source_product.source_code,
                            purchase_index,
                            purchase.status,
                        )
                        continue

                    try:
                        purchase.status = "processing"
                        purchase.error_message = None
                        self.db.commit()

                        log.info(
                            "AutoAlliance order create request: posting=%s offer_id=%s source_code=%s unit=%s",
                            posting.posting_number,
                            product.offer_id,
                            source_product.source_code,
                            purchase_index,
                        )

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

                        log.info(
                            "AutoAlliance purchase done posting=%s offer_id=%s source_code=%s unit=%s",
                            posting.posting_number,
                            product.offer_id,
                            source_product.source_code,
                            purchase_index,
                        )

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
                            "AutoAlliance purchase failed posting=%s offer_id=%s source_code=%s unit=%s error=%s",
                            posting.posting_number,
                            product.offer_id,
                            source_product.source_code,
                            purchase_index,
                            exc,
                        )

                    await asyncio.sleep(self.delay)

        log.info("AutoAlliance purchase finished with stats: %s", stats.as_dict())
        return stats.as_dict()


    def _list_posting_products(self):
        stmt = (
            select(OzonPosting, OzonPostingProduct)
            .join(OzonPostingProduct, OzonPostingProduct.posting_id == OzonPosting.id)
            .where(OzonPosting.status == "awaiting_packaging")
            .order_by(OzonPosting.in_process_at.asc())
        )

        return self.db.execute(stmt).all()


    def _find_source_product(self, product: OzonPostingProduct) -> SourceProduct | None:
        log.info(
            "Match search: offer_id=%s manufacturer_article=%s",
            product.offer_id,
            product.manufacturer_article,
        )
        values = {
            str(product.offer_id or "").strip(),
            str(product.manufacturer_article or "").strip(),
        }
        values.discard("")

        if not values:
            return None

        products = list(
            self.db.scalars(
                select(SourceProduct).where(
                    SourceProduct.source_code.is_not(None),
                    or_(
                        SourceProduct.article.in_(values),
                        SourceProduct.manufacturer_article.in_(values),
                        SourceProduct.factory_article.in_(values),
                    ),
                )
            )
        )

        if not products:
            return None

        offer_id = str(product.offer_id or "").strip()
        manufacturer_article = str(product.manufacturer_article or "").strip()

        def score(item: SourceProduct) -> int:
            if item.article == offer_id:
                return 100
            if item.manufacturer_article == offer_id:
                return 90
            if item.factory_article == offer_id:
                return 80
            if manufacturer_article and item.manufacturer_article == manufacturer_article:
                return 70
            if manufacturer_article and item.article == manufacturer_article:
                return 60
            if manufacturer_article and item.factory_article == manufacturer_article:
                return 50
            return 0
        
        log.info(
            "Found %s source candidates",
            len(products),
        )

        return sorted(products, key=score, reverse=True)[0]


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
