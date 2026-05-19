from __future__ import annotations
import asyncio
import logging
from dataclasses import dataclass
from typing import Iterable, TypeVar
import httpx
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from src.app.config import settings
from src.autoalliance.client import AutoAllianceClient
from src.autoalliance.models import SourceProduct
from src.ozon.client import OzonClient
from src.ozon.models import OzonProduct, OzonShop
from src.ozon.pricing import calc_ozon_price
from src.ozon.repository import OzonRepository
from src.ozon.service import OzonProductImportService


log = logging.getLogger(__name__)

# Список складов AutoAlliance для расчета остатка.
# Если нужно несколько складов, просто добавь название в список.
AUTOALLIANCE_STOCK_WAREHOUSES = ["Машково"]


@dataclass(slots=True)
class ProductSyncRow:
    ozon_product: OzonProduct
    source_product: SourceProduct
    search_article: str
    search_brand: str


@dataclass(slots=True)
class ShopSyncStats:
    shop: str
    candidates: int = 0
    autoalliance_found: int = 0
    price_calculated: int = 0
    price_sent: int = 0
    stock_sent: int = 0
    skipped: int = 0
    failed: int = 0

    def as_dict(self) -> dict:
        return {
            "shop": self.shop,
            "candidates": self.candidates,
            "autoalliance_found": self.autoalliance_found,
            "price_calculated": self.price_calculated,
            "price_sent": self.price_sent,
            "stock_sent": self.stock_sent,
            "skipped": self.skipped,
            "failed": self.failed,
        }


T = TypeVar("T")


def chunked(items: list[T], size: int) -> Iterable[list[T]]:
    for i in range(0, len(items), size):
        yield items[i:i + size]


def _clean(value: object) -> str:
    return str(value or "").strip()


def _to_float(value: object) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(str(value).replace(" ", "").replace(",", "."))
    except Exception:
        return None


def _to_int(value: object) -> int:
    number = _to_float(value)
    if number is None:
        return 0
    return max(0, int(number))


def _commission_to_fraction(value: float | None) -> float:
    if value is None:
        return 0.14
    value = float(value)
    if value > 1:
        return value / 100
    return value


def _volume_liters_from_mm(
    *,
    length_mm: int | None,
    width_mm: int | None,
    height_mm: int | None,
) -> float | None:
    if not length_mm or not width_mm or not height_mm:
        return None
    return float(length_mm) * float(width_mm) * float(height_mm) / 1_000_000


def _warehouse_names() -> list[str]:
    return [item.strip().lower() for item in AUTOALLIANCE_STOCK_WAREHOUSES if item.strip()]


def _quantity_by_warehouses(offer: dict, warehouse_names: list[str]) -> int:
    if not warehouse_names:
        return _to_int(offer.get("quantity"))

    total = 0
    for warehouse in offer.get("warehouses") or []:
        name = str(warehouse.get("name") or "").lower()
        if any(expected in name for expected in warehouse_names):
            total += _to_int(warehouse.get("quantity"))

    return total


class PriceStockSyncService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.ozon_repo = OzonRepository(db)
        self.ozon_import_service = OzonProductImportService(self.ozon_repo)


    async def sync_all_shops(self) -> list[dict]:
        results: list[dict] = []
        shops = self.ozon_repo.list_active_shops()
        log.info("Price/stock sync: active shops=%s", len(shops))

        for shop in shops:
            stats = await self.sync_shop(shop)
            results.append(stats.as_dict())

        return results


    async def sync_shop(self, shop: OzonShop) -> ShopSyncStats:
        stats = ShopSyncStats(shop=shop.shop_name)
        log.info("Price/stock sync shop started: shop_id=%s shop=%s warehouse=%s", shop.id, shop.shop_name, shop.warehouse)

        if not shop.warehouse:
            stats.failed += 1
            log.error("Price/stock sync skipped: shop=%s has no warehouse", shop.shop_name)
            log.info("Price/stock sync shop finished: %s", stats.as_dict())
            return stats

        # 1. Сначала обновляем локальную базу данными Ozon.
        await self.ozon_import_service.import_shop_products(shop)
        await self._refresh_ozon_product_details(shop)

        rows = self._list_sync_rows(shop)
        stats.candidates = len(rows)
        log.info("Price/stock candidates: shop=%s count=%s", shop.shop_name, stats.candidates)

        if not rows:
            log.warning("Price/stock sync skipped: shop=%s has no candidates", shop.shop_name)
            log.info("Price/stock sync shop finished: %s", stats.as_dict())
            return stats

        headers = {}
        if settings.autoalliance_api_key:
            headers["Authorization"] = f"Bearer {settings.autoalliance_api_key}"


        async with httpx.AsyncClient(
            base_url=settings.autoalliance_base_url,
            headers=headers,
            timeout=settings.autoalliance_timeout,
        ) as http_client:
            auto_client = AutoAllianceClient(http_client)

            for batch in chunked(rows, 100):
                payload = [
                    {
                        "article": row.search_article,
                        "brand": row.search_brand,
                    }
                    for row in batch
                ]

                log.info("AutoAlliance batch request: shop=%s batch_size=%s", shop.shop_name, len(batch))

                try:
                    response_items = await auto_client.search_parts_batch(payload, analogs=False)
                    log.info("AutoAlliance batch response: shop=%s items=%s", shop.shop_name, len(response_items))
                except Exception as exc:
                    stats.failed += len(batch)
                    log.exception(
                        "AutoAlliance batch failed shop=%s size=%s error=%s",
                        shop.shop_name,
                        len(batch),
                        exc,
                    )
                    continue

                response_by_key = {
                    (_clean(item.get("article")), _clean(item.get("brand"))): item
                    for item in response_items
                }

                for row in batch:
                    item = response_by_key.get((row.search_article, row.search_brand))
                    offer = (item or {}).get("offer") or {}

                    if not offer:
                        stats.skipped += 1
                        row.ozon_product.supplier_qty = 0
                        log.warning("AutoAlliance offer not found: shop=%s offer_id=%s article=%s brand=%s", shop.shop_name, row.ozon_product.offer_id, row.search_article, row.search_brand)
                        continue

                    try:
                        self._apply_supplier_data(row.ozon_product, offer)
                        stats.autoalliance_found += 1

                        if self._calculate_price(row.ozon_product):
                            stats.price_calculated += 1
                        else:
                            stats.skipped += 1

                    except Exception as exc:
                        stats.failed += 1
                        log.exception(
                            "Product calc failed shop=%s offer_id=%s error=%s",
                            shop.shop_name,
                            row.ozon_product.offer_id,
                            exc,
                        )

                self.db.commit()
                await asyncio.sleep(0.2)

        # 2. После сохранения в БД отправляем сначала цены, потом остатки.
        log.info("Sending Ozon prices: shop=%s", shop.shop_name)
        stats.price_sent = await self._send_prices(shop)
        log.info("Sending Ozon stocks: shop=%s", shop.shop_name)
        stats.stock_sent = await self._send_stocks(shop)

        self.ozon_repo.add_sync_log(
            shop_id=shop.id,
            sync_type="price_stock_sync",
            status="done" if stats.failed == 0 else "partial",
            message=f"Price/stock sync finished for shop={shop.shop_name}",
            items_total=stats.candidates,
            items_success=stats.price_sent + stats.stock_sent,
            items_failed=stats.failed,
        )

        log.info("Price/stock sync shop finished: %s", stats.as_dict())
        return stats


    async def _refresh_ozon_product_details(self, shop: OzonShop) -> None:
        products = self.ozon_repo.list_products_for_details_import(
            shop_id=shop.id,
            only_empty=False,
            limit=None,
        )
        product_ids = [int(product.product_id) for product in products if product.product_id]

        if not product_ids:
            return


        async with httpx.AsyncClient(timeout=60) as http_client:
            client = OzonClient(http_client=http_client, shop=shop)
            for batch in chunked(product_ids, 100):
                try:
                    items = await client.get_product_attributes(product_ids=batch, limit=100)
                    for item in items:
                        self.ozon_repo.update_product_details_from_ozon_attributes(item=item)
                    self.db.commit()
                except Exception as exc:
                    self.db.rollback()
                    log.exception(
                        "Ozon details refresh failed shop=%s batch_first=%s error=%s",
                        shop.shop_name,
                        batch[:3],
                        exc,
                    )
                await asyncio.sleep(0.2)


    def _list_sync_rows(self, shop: OzonShop) -> list[ProductSyncRow]:
        products = list(
            self.db.scalars(
                select(OzonProduct).where(
                    OzonProduct.shop_id == shop.id,
                    OzonProduct.archived.is_(False),
                    OzonProduct.offer_id.is_not(None),
                    OzonProduct.moderate_status == "approved",
                ).order_by(OzonProduct.id)
            )
        )

        rows: list[ProductSyncRow] = []

        for product in products:
            offer_id = _clean(product.offer_id)
            if not offer_id:
                continue

            source_product = self.db.scalar(
                select(SourceProduct).where(
                    or_(
                        SourceProduct.article == offer_id,
                        SourceProduct.manufacturer_article == offer_id,
                        SourceProduct.factory_article == offer_id,
                    )
                )
            )

            if source_product is None:
                continue

            brand = _clean(source_product.source_brand)
            if not brand:
                continue

            search_article = (
                _clean(source_product.article)
                or _clean(source_product.manufacturer_article)
                or _clean(source_product.factory_article)
                or offer_id
            )

            rows.append(
                ProductSyncRow(
                    ozon_product=product,
                    source_product=source_product,
                    search_article=search_article,
                    search_brand=brand,
                )
            )

        return rows


    def _apply_supplier_data(self, product: OzonProduct, offer: dict) -> None:
        product.supplier_price_rub = _to_float(offer.get("price"))
        product.supplier_qty = _quantity_by_warehouses(offer, _warehouse_names())
        product.stock = product.supplier_qty


    def _calculate_price(self, product: OzonProduct) -> bool:
        if not product.supplier_price_rub:
            return False

        volume = _volume_liters_from_mm(
            length_mm=product.length_mm,
            width_mm=product.width_mm,
            height_mm=product.height_mm,
        )

        if not volume:
            return False

        product.price_calc = calc_ozon_price(
            base=product.supplier_price_rub,
            volume=volume,
            commission=_commission_to_fraction(product.fbs_commission_percent),
        )
        return True


    async def _send_prices(self, shop: OzonShop) -> int:
        products = list(
            self.db.scalars(
                select(OzonProduct).where(
                    OzonProduct.shop_id == shop.id,
                    OzonProduct.archived.is_(False),
                    OzonProduct.offer_id.is_not(None),
                    OzonProduct.price_calc.is_not(None),
                ).order_by(OzonProduct.id)
            )
        )

        sent = 0
        async with httpx.AsyncClient(timeout=60) as http_client:
            client = OzonClient(http_client=http_client, shop=shop)

            for batch in chunked(products, 100):
                payload = [
                    {
                        "offer_id": product.offer_id,
                        "price": str(int(product.price_calc)),
                        "old_price": str(int(product.price_calc * 1.2)),
                    }
                    for product in batch
                    if product.price_calc
                ]

                if not payload:
                    continue

                result = await client.update_prices(payload)
                log.info("Ozon prices updated shop=%s sent=%s result=%s", shop.shop_name, len(payload), result)

                for product in batch:
                    if product.price_calc:
                        product.price_current = float(product.price_calc)
                        product.price = float(product.price_calc)

                self.db.commit()
                sent += len(payload)
                await asyncio.sleep(0.3)

        return sent


    async def _send_stocks(self, shop: OzonShop) -> int:
        products = list(
            self.db.scalars(
                select(OzonProduct).where(
                    OzonProduct.shop_id == shop.id,
                    OzonProduct.archived.is_(False),
                    OzonProduct.offer_id.is_not(None),
                    OzonProduct.supplier_qty.is_not(None),
                ).order_by(OzonProduct.id)
            )
        )

        sent = 0
        async with httpx.AsyncClient(timeout=60) as http_client:
            client = OzonClient(http_client=http_client, shop=shop)

            for batch in chunked(products, 100):
                payload = [
                    {
                        "offer_id": product.offer_id,
                        "stock": int(product.supplier_qty or 0),
                        "warehouse_id": shop.warehouse,
                    }
                    for product in batch
                ]

                if not payload:
                    continue

                result = await client.update_stocks(payload)
                log.info("Ozon stocks updated shop=%s sent=%s result=%s", shop.shop_name, len(payload), result)

                for product in batch:
                    product.stock = int(product.supplier_qty or 0)
                    product.warehouse_id = shop.warehouse

                self.db.commit()
                sent += len(payload)
                await asyncio.sleep(0.3)

        return sent
