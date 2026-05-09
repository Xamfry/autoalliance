from pathlib import Path

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from src.autoalliance.models import AutoAllianceProduct


def _join_urls(value) -> str:
    if not value:
        return ""

    if isinstance(value, list):
        return ", ".join(str(x).strip() for x in value if str(x).strip())

    return str(value)


def _safe_sheet_name(name: str) -> str:
    bad_chars = ["\\", "/", "*", "[", "]", ":", "?"]
    for ch in bad_chars:
        name = name.replace(ch, "_")

    name = name.strip() or "Без категории"
    return name[:31]


def _category_name(product: AutoAllianceProduct) -> str:
    if product.catalog_group:
        return product.catalog_group

    if product.manual_category:
        return product.manual_category

    return "Без категории"


def _list_to_text(value) -> str:
    if not value:
        return ""

    if isinstance(value, list):
        return ", ".join(str(x).strip() for x in value if str(x).strip())

    return str(value)


def _product_to_row(product: AutoAllianceProduct) -> dict:
    source = product.source_product

    return {
        "Код товара": source.source_code,
        "Артикул": source.article,
        "Артикул производителя": source.manufacturer_article,
        "Артикул завода": source.factory_article,
        "Название": source.source_name,
        "Производитель": source.source_brand,

        "Цена": product.price,
        "Категория": product.catalog_group,
        "Подкатегория": product.catalog_subgroup,

        "ТН ВЭД": product.tnved,

        "Картинки": _join_urls(product.pictures_json),
        "Картинки без водяного знака": _join_urls(product.pictures_without_watermark_json),

        "Описание": product.description_text,
        
        "Применяемость": _list_to_text([
            f"{x.get('markName', '')} {x.get('modelName', '')}".strip()
            for x in (product.preview_applicabilities_json or [])
            if isinstance(x, dict)
        ]),

        "Ширина, м": product.preview_width,
        "Высота, м": product.preview_height,
        "Длина, м": product.preview_length,
        "Вес, кг": product.preview_weight,

        "Ссылка на сайт": product.site_url,
    }
    
ONLY_FOUND_EXCLUDE_COLUMNS = [
    "Ручная категория",
    "Ручная подкатегория",
    "Штрихкод",
    "Статус парсинга",
    "Найдено по",
    "Искомый артикул",
    "Искомый бренд",
    "Ошибка",
]

def _filter_columns_for_only_found(df: pd.DataFrame) -> pd.DataFrame:
    return df.drop(
        columns=[col for col in ONLY_FOUND_EXCLUDE_COLUMNS if col in df.columns]
    )


def export_autoalliance_products_to_excel(
    db: Session,
    *,
    output_path: str,
    only_found: bool = False,
) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    query = (
        select(AutoAllianceProduct)
        .options(joinedload(AutoAllianceProduct.source_product))
        .order_by(AutoAllianceProduct.catalog_group, AutoAllianceProduct.catalog_subgroup)
    )

    if only_found:
        query = query.where(AutoAllianceProduct.parse_status == "found")

    products = list(db.scalars(query))

    rows = [_product_to_row(product) for product in products]
    df_all = pd.DataFrame(rows)
    if only_found:
        df_all = _filter_columns_for_only_found(df_all)

    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        df_all.to_excel(writer, sheet_name="Все товары", index=False)

        found_products = [
            product for product in products
            if product.parse_status == "found"
        ]

        categories = sorted(set(_category_name(product) for product in found_products))

        for category in categories:
            category_rows = [
                _product_to_row(product)
                for product in found_products
                if _category_name(product) == category
            ]

            df_category = pd.DataFrame(category_rows)
            if only_found:
                df_category = _filter_columns_for_only_found(df_category)
            df_category.to_excel(
                writer,
                sheet_name=_safe_sheet_name(category),
                index=False,
            )

        error_products = [
            product for product in products
            if product.parse_status != "found"
        ]

        if error_products:
            df_errors = pd.DataFrame(
                [_product_to_row(product) for product in error_products]
            )
            df_errors.to_excel(writer, sheet_name="Ошибки", index=False)

    return path