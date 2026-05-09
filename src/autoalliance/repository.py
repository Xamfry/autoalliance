from bs4 import BeautifulSoup
from sqlalchemy import select
from sqlalchemy.orm import Session
from urllib.parse import urljoin
from src.autoalliance.models import AutoAllianceProduct, SourceProduct

AUTOOPT_SITE_BASE_URL = "https://www.autoopt.ru/"

def _to_float(value) -> float | None:
    try:
        if value is None:
            return None
        value = str(value).strip().replace(" ", "").replace(",", ".")
        if not value:
            return None
        return float(value)
    except Exception:
        return None


def _to_int(value) -> int | None:
    try:
        number = _to_float(value)
        if number is None:
            return None
        return int(number)
    except Exception:
        return None


def _html_to_text(html: str | None) -> str | None:
    if not html:
        return None
    return BeautifulSoup(html, "html.parser").get_text(" ", strip=True)


def _first(items) -> str | None:
    if isinstance(items, list) and items:
        return items[0]
    return None


def _main_property_value(good: dict, name: str):
    for prop in good.get("main_properties") or []:
        if prop.get("name") == name:
            return prop.get("value")
    return None

class AutoAllianceRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def upsert_source_product_from_row(self, row: dict) -> SourceProduct:
        source_code = str(row.get("Код товара") or "").strip()

        product = None

        if source_code:
            product = self.db.scalar(
                select(SourceProduct).where(SourceProduct.source_code == source_code)
            )

        if product is None:
            product = SourceProduct(source_code=source_code)
            self.db.add(product)

        product.article = row.get("Артикул")
        product.manufacturer_article = row.get("Артикул производителя")
        product.factory_article = row.get("Артикул завода")
        product.source_name = row.get("Наименование товара")
        product.source_brand = row.get("Производитель")

        product.opt4_price = _to_float(row.get("ОПТ4"))
        product.opt3_price = _to_float(row.get("ОПТ3"))
        product.opt2_price = _to_float(row.get("ОПТ2"))
        product.opt1_price = _to_float(row.get("ОПТ1"))
        product.retail_price = _to_float(row.get("Розница"))

        product.stock_mashkovo = _to_int(row.get("Остаток Машково"))
        product.stock_ketcherskaya = _to_int(row.get("Остаток Кетчерская"))
        product.stock_other = _to_int(row.get("Остаток Прочие"))

        self.db.flush()
        return product
    
    def save_found_product(
        self,
        *,
        source_product: SourceProduct,
        matched_by: str,
        search_article: str,
        search_brand: str,
        response_item: dict,
    ) -> AutoAllianceProduct:
        offer = response_item.get("offer") or {}
        analogs = response_item.get("analogs") or []

        properties = offer.get("properties") or {}
        catalog = properties.get("catalog") or {}

        supplier_code = str(offer.get("code") or "").strip()

        product = None
        if supplier_code:
            product = self.db.scalar(
                select(AutoAllianceProduct).where(
                    AutoAllianceProduct.source_product_id == source_product.id,
                    AutoAllianceProduct.supplier_code == supplier_code,
                )
            )

        if product is None:
            product = AutoAllianceProduct(
                source_product_id=source_product.id,
                supplier_code=supplier_code,
            )
            self.db.add(product)

        product.parse_status = "found"
        product.matched_by = matched_by
        product.search_article = search_article
        product.search_brand = search_brand
        product.error_message = None

        product.supplier_article = offer.get("article")
        product.supplier_brand = offer.get("brand")
        product.supplier_name = offer.get("name")

        product.price = _to_float(offer.get("price"))
        product.quantity = _to_int(offer.get("quantity"))
        product.for_order = offer.get("for_order")
        product.can_return = offer.get("can_return")

        product.tnved = properties.get("tnved")
        product.description_html = properties.get("description")
        product.description_text = _html_to_text(properties.get("description"))

        product.catalog_group = catalog.get("group")
        product.catalog_subgroup = catalog.get("subgroup")

        product.width = _to_float(properties.get("width_m"))
        product.height = _to_float(properties.get("height_m"))
        product.length = _to_float(properties.get("length_m"))
        product.weight = _to_float(properties.get("weight_kg"))
        product.barcode = properties.get("barcode")

        pictures = properties.get("pictures") or []
        clean_pictures = properties.get("pictures_without_watermark") or []

        product.site_url = properties.get("site_url")
        product.first_picture_url = _first(clean_pictures) or _first(pictures)

        product.pictures_json = pictures
        product.pictures_without_watermark_json = clean_pictures
        product.warehouses_json = offer.get("warehouses") or []
        product.analogs_json = analogs

        self.db.flush()
        return product

    def save_not_found(
        self,
        *,
        source_product: SourceProduct,
        matched_by: str,
        search_article: str,
        search_brand: str,
        error_message: str | None = None,
    ) -> AutoAllianceProduct:
        product = AutoAllianceProduct(
            source_product_id=source_product.id,
            parse_status="not_found",
            matched_by=matched_by,
            search_article=search_article,
            search_brand=search_brand,
            error_message=error_message,
        )

        self.db.add(product)
        self.db.flush()
        return product
    
    def update_product_preview_from_json(
        self,
        *,
        product: AutoAllianceProduct,
        preview: dict,
    ) -> AutoAllianceProduct:
        good = preview.get("good") or {}

        product.preview_applicabilities_json = good.get("applicabilities") or []
        product.preview_certificates_json = good.get("certificates") or []
        
        if good.get("url"):
            product.preview_url = urljoin(
                urljoin(AUTOOPT_SITE_BASE_URL, "/catalog/"),
                good.get("url"),
            )

        product.preview_images_json = [
            urljoin(AUTOOPT_SITE_BASE_URL, path)
            for path in good.get("big_pictures") or []
        ]

        product.preview_width = _to_float(_main_property_value(good, "Ширина, м"))
        product.preview_height = _to_float(_main_property_value(good, "Высота, м"))
        product.preview_length = _to_float(_main_property_value(good, "Длина, м"))
        product.preview_weight = _to_float(_main_property_value(good, "Вес, кг"))

        self.db.flush()
        return product