import asyncio
import logging
import httpx
from sqlalchemy.orm import Session

from src.ozon.client import OzonClient
from src.ozon.models import OzonShop
from src.ozon.repository import OzonRepository
from src.ozon.schemas.posting_request import PostingRequest
from src.ozon.schemas.posting_split_request import PostingSplitRequest


log = logging.getLogger(__name__)


class PostingSyncService:
    def __init__(self, db: Session, *, delay: float = 0.3) -> None:
        self.db = db
        self.repository = OzonRepository(db)
        self.delay = delay


    async def sync_shop_postings(self, shop: OzonShop, *, days: int = 7) -> dict:
        stats = {
            "shop": shop.shop_name,
            "postings_total": 0,
            "grouped_found": 0,
            "split_ok": 0,
            "split_failed": 0,
            "saved": 0,
        }

        log.info("Posting sync shop started: shop_id=%s shop=%s days=%s", shop.id, shop.shop_name, days)

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
            client = OzonClient(http_client=http_client, shop=shop)

            request = PostingRequest.since_days_request(days)
            response = await client.get_all_postings(request)

            all_postings = response.get_all_postings()
            grouped_postings = response.get_new_grouped_postings()

            stats["postings_total"] = len(all_postings)
            stats["grouped_found"] = len(grouped_postings)
            log.info(
                "Posting sync fetched: shop=%s postings_total=%s grouped_found=%s",
                shop.shop_name,
                stats["postings_total"],
                stats["grouped_found"],
            )

            for posting in grouped_postings:
                try:
                    split_products = posting.get_split_products()

                    log.info(
                        "Posting split started: shop=%s posting=%s products=%s",
                        shop.shop_name,
                        posting.posting_number,
                        len(split_products),
                    )

                    split_request = PostingSplitRequest.from_posting_products(
                        posting_number=posting.posting_number,
                        posting_response_products=split_products,
                    )

                    await client.split_posting(split_request)
                    stats["split_ok"] += 1

                    await asyncio.sleep(self.delay)

                except Exception as exc:
                    stats["split_failed"] += 1
                    log.exception(
                        "Split failed shop=%s posting=%s error=%s",
                        shop.shop_name,
                        posting.posting_number,
                        exc,
                    )

            response_after_split = await client.get_all_postings(request)

            saved = self.repository.upsert_postings(
                shop=shop,
                postings=response_after_split.get_single_postings(),
            )

            self.db.commit()
            stats["saved"] = saved
            log.info("Posting sync saved: shop=%s saved=%s", shop.shop_name, saved)

        log.info("Posting sync shop finished: %s", stats)
        return stats


    async def sync_all_shops(self, *, days: int = 7, shop_name: str | None = None) -> list[dict]:
        shops = self.repository.list_shops()
        log.info("Posting sync shops loaded: count=%s shop_filter=%s", len(shops), shop_name)

        if shop_name:
            shops = [shop for shop in shops if shop.shop_name == shop_name]

        results = []

        for shop in shops:
            result = await self.sync_shop_postings(shop, days=days)
            results.append(result)

        return results