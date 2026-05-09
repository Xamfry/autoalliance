from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session
from src.ozon.models import (OzonProduct, OzonShop, 
                             OzonSyncLog, OzonPosting, 
                             OzonPostingProduct)

from src.autoalliance.models import SourceProduct


def _to_float(value):
    if value in (None, ""):
        return None
    try:
        return float(str(value).replace(" ", "").replace(",", "."))
    except Exception:
        return None


def _get_first_image_url(item: dict) -> str | None:
    primary = item.get("primary_image")
    if isinstance(primary, list) and primary:
        return primary[0]

    images = item.get("images")
    if isinstance(images, list) and images:
        return images[0]

    return None


def _get_commission_percent(item: dict, schema: str) -> float | None:
    for commission in item.get("commissions") or []:
        if commission.get("sale_schema") == schema:
            value = commission.get("percent")
            return float(value) if value is not None else None
    return None


def _to_int_or_none(value) -> int | None:
    try:
        if value is None:
            return None

        value = str(value).strip().replace(" ", "").replace(",", ".")

        if not value:
            return None

        return int(float(value))
    except Exception:
        return None


def _extract_int_by_keys(item: dict, keys: list[str]) -> int | None:
    for key in keys:
        value = item.get(key)
        parsed = _to_int_or_none(value)
        if parsed is not None:
            return parsed

    return None


class OzonRepository:
    def __init__(self, db: Session) -> None:
        self.db = db


    def create_or_update_shop(self, *, shop_name: str, client_id: str, token: str, warehouse: int | None = None) -> OzonShop:
        shop = self.db.scalar(select(OzonShop).where(OzonShop.shop_name == shop_name))
        if shop is None:
            shop = OzonShop(shop_name=shop_name, client_id=client_id, token=token, warehouse=warehouse, is_active=True)
            self.db.add(shop)
        else:
            shop.client_id = client_id
            shop.token = token
            shop.warehouse = warehouse
            shop.is_active = True
        self.db.commit()
        self.db.refresh(shop)
        return shop


    def get_shop_by_name(self, shop_name: str) -> OzonShop | None:
        return self.db.scalar(select(OzonShop).where(OzonShop.shop_name == shop_name))


    def list_active_shops(self) -> list[OzonShop]:
        return list(self.db.scalars(select(OzonShop).where(OzonShop.is_active.is_(True)).order_by(OzonShop.id)))


    def upsert_product_from_ozon_item(self, *, shop: OzonShop, item: dict) -> OzonProduct:
        offer_id = str(item.get("offer_id") or "").strip()
        if not offer_id:
            raise ValueError("Ozon product item has empty offer_id")

        product = self.db.scalar(
            select(OzonProduct).where(
                OzonProduct.shop_id == shop.id,
                OzonProduct.offer_id == offer_id,
            )
        )

        if product is None:
            product = OzonProduct(shop_id=shop.id, offer_id=offer_id)
            self.db.add(product)

        statuses = item.get("statuses") or {}
        stocks = item.get("stocks") or {}
        product.product_id = item.get("id") or item.get("product_id")
        product.sku = item.get("sku") or item.get("fbo_sku") or item.get("fbs_sku")
        product.name = item.get("name")
        product.category_id = item.get("category_id")
        product.description_category_id = item.get("description_category_id")
        product.first_image_url = _get_first_image_url(item)
        product.archived = bool(item.get("is_archived") or item.get("archived") or False)
        product.visible = item.get("visible")
        product.moderate_status = (
            statuses.get("moderate_status")
            or item.get("moderate_status")
            or item.get("status")
        )

        price = item.get("price")
        if isinstance(price, dict):
            product.price = _to_float(price.get("price"))
        else:
            product.price = _to_float(price)

        product.barcodes_json = item.get("barcodes") or []
        product.fbs_commission_percent = _get_commission_percent(item, "FBS")
        product.fbo_commission_percent = _get_commission_percent(item, "FBO")
        product.rfbs_commission_percent = _get_commission_percent(item, "RFBS")
        product.fbp_commission_percent = _get_commission_percent(item, "FBP")
        product.stocks_json = stocks.get("stocks") or []
        product.has_stock = bool(stocks.get("has_stock"))
        product.raw_json = item

        return product


    def add_sync_log(self, *, shop_id: int | None, sync_type: str, status: str, 
                     message: str | None = None, items_total: int = 0, 
                     items_success: int = 0, items_failed: int = 0) -> OzonSyncLog:
        log = OzonSyncLog(shop_id=shop_id, sync_type=sync_type, status=status, 
                          message=message, items_total=items_total, 
                          items_success=items_success, items_failed=items_failed)
        self.db.add(log)
        self.db.commit()
        return log
    
    
    def list_shops(self) -> list[OzonShop]:
        return list(self.db.scalars(select(OzonShop).order_by(OzonShop.id)))


    def count_products_by_shop_id(self, shop_id: int) -> int:
        return int(
            self.db.scalar(
                select(func.count(OzonProduct.id)).where(OzonProduct.shop_id == shop_id)
            )
            or 0
        )


    def delete_shop_with_products(self, shop_id: int) -> bool:
        shop = self.db.get(OzonShop, shop_id)
        if shop is None:
            return False

        self.db.execute(delete(OzonProduct).where(OzonProduct.shop_id == shop_id))
        self.db.delete(shop)
        self.db.commit()
        return True


    def list_products_for_details_import(
        self,
        *,
        shop_id: int | None = None,
        only_empty: bool = False,
        limit: int | None = None,
    ) -> list[OzonProduct]:
        query = select(OzonProduct).where(OzonProduct.product_id.is_not(None))

        if shop_id is not None:
            query = query.where(OzonProduct.shop_id == shop_id)

        if only_empty:
            query = query.where(
                (OzonProduct.length_mm.is_(None))
                | (OzonProduct.width_mm.is_(None))
                | (OzonProduct.height_mm.is_(None))
                | (OzonProduct.weight_g.is_(None))
            )

        query = query.order_by(OzonProduct.id)

        if limit:
            query = query.limit(limit)

        return list(self.db.scalars(query))


    def update_product_details_from_ozon_attributes(
        self,
        *,
        item: dict,
    ) -> bool:
        product_id = item.get("id") or item.get("product_id")

        if not product_id:
            return False

        product = self.db.scalar(
            select(OzonProduct).where(OzonProduct.product_id == int(product_id))
        )

        if product is None:
            return False

        product.length_mm = _extract_int_by_keys(
            item,
            ["depth", "length", "dimension_depth", "length_mm"],
        )
        product.width_mm = _extract_int_by_keys(
            item,
            ["width", "dimension_width", "width_mm"],
        )
        product.height_mm = _extract_int_by_keys(
            item,
            ["height", "dimension_height", "height_mm"],
        )
        product.weight_g = _extract_int_by_keys(
            item,
            ["weight", "weight_g"],
        )

        return True
    

    def upsert_postings(self, *, shop: OzonShop, postings: list) -> int:
        saved = 0

        for posting_item in postings:
            posting = self.db.scalar(
                select(OzonPosting).where(
                    OzonPosting.posting_number == posting_item.posting_number
                )
            )

            if posting is None:
                posting = OzonPosting(
                    shop_id=shop.id,
                    posting_number=posting_item.posting_number,
                )
                self.db.add(posting)
                self.db.flush()

            posting.shop_id = shop.id
            posting.order_id = posting_item.order_id
            posting.order_number = posting_item.order_number
            posting.status = posting_item.status
            posting.substatus = posting_item.substatus
            posting.in_process_at = posting_item.in_process_at
            posting.shipment_date = posting_item.shipment_date
            posting.raw_json = posting_item.model_dump(mode="json")

            self.db.query(OzonPostingProduct).filter(
                OzonPostingProduct.posting_id == posting.id
            ).delete()

            for product_item in posting_item.products:
                ozon_product = self.db.scalar(
                    select(OzonProduct).where(
                        OzonProduct.shop_id == shop.id,
                        OzonProduct.offer_id == product_item.offer_id,
                    )
                )

                source_product = self.db.scalar(
                    select(SourceProduct).where(
                        SourceProduct.article == product_item.offer_id
                    )
                )

                posting_product = OzonPostingProduct(
                    posting_id=posting.id,
                    offer_id=product_item.offer_id,
                    sku=product_item.sku,
                    name=product_item.name,
                    quantity=product_item.quantity,
                    image_url=ozon_product.first_image_url if ozon_product else None,
                    manufacturer_article=(
                        source_product.manufacturer_article
                        if source_product
                        else None
                    ),
                )

                self.db.add(posting_product)

            saved += 1

        self.db.flush()
        return saved