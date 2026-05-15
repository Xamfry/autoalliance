import logging
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from src.app.db import SessionLocal
from src.ozon.sync.posting_sync_service import PostingSyncService
from src.ozon.sync.price_stock_sync_service import PriceStockSyncService
from src.autoalliance.purchase_service import AutoAlliancePurchaseService


log = logging.getLogger(__name__)


async def sync_postings_job(days: int = 7) -> None:
    started_at = datetime.now()

    with SessionLocal() as db:
        service = PostingSyncService(db)

        try:
            results = await service.sync_all_shops(days=days)

            for result in results:
                log.info("Posting sync result: %s", result)

        except Exception as exc:
            log.exception("Posting sync failed: %s", exc)

    finished_at = datetime.now()
    log.info("Posting sync finished in %s", finished_at - started_at)


async def sync_price_stock_job() -> None:
    started_at = datetime.now()

    with SessionLocal() as db:
        service = PriceStockSyncService(db)

        try:
            results = await service.sync_all_shops()

            for result in results:
                log.info("Price/stock sync result: %s", result)

        except Exception as exc:
            log.exception("Price/stock sync failed: %s", exc)

    finished_at = datetime.now()
    log.info("Price/stock sync finished in %s", finished_at - started_at)


async def purchase_new_postings_job() -> None:
    started_at = datetime.now()

    with SessionLocal() as db:
        service = AutoAlliancePurchaseService(db)

        try:
            result = await service.purchase_new_postings()
            log.info("AutoAlliance purchase result: %s", result)

        except Exception as exc:
            log.exception("AutoAlliance purchase failed: %s", exc)

    finished_at = datetime.now()
    log.info("AutoAlliance purchase finished in %s", finished_at - started_at)


def create_scheduler(
    *,
    interval_seconds: int = 60,
    days: int = 7,
    price_stock_interval_seconds: int = 10800,
) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler()

    scheduler.add_job(
        sync_postings_job,
        trigger="interval",
        seconds=interval_seconds,
        kwargs={"days": days},
        id="ozon_postings_sync",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )

    scheduler.add_job(
        sync_price_stock_job,
        trigger="interval",
        seconds=price_stock_interval_seconds,
        id="ozon_price_stock_sync",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    
    scheduler.add_job(
        purchase_new_postings_job,
        trigger="interval",
        seconds=60,
        id="autoalliance_purchase_new_postings",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )

    return scheduler
