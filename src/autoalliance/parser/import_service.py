import logging
import asyncio
import httpx
import pandas as pd
from tqdm import tqdm
from pathlib import Path

from src.app.config import settings
from src.app.db import SessionLocal
from src.autoalliance.client import AutoAllianceClient
from src.autoalliance.repository import AutoAllianceRepository


log = logging.getLogger(__name__)


ARTICLE_STEPS = [
    ("article", "article", "Артикул"),
    ("manufacturer_article", "manufacturer_article", "Артикул производителя"),
    ("factory_article", "factory_article", "Артикул завода"),
]


REQUIRED_COLUMNS = [
    "Код товара",
    "Артикул",
    "Артикул производителя",
    "Артикул завода",
    "Наименование товара",
    "Производитель",
]


def clean_value(value) -> str:
    if value is None:
        return ""

    value = str(value).strip()

    if not value:
        return ""

    if value.lower() in {"nan", "none", "null"}:
        return ""

    # Excel bug:
    # 12345.0 -> 12345
    # ABC-123.0 -> ABC-123
    if value.endswith(".0"):
        value = value[:-2]

    return value.strip()


def read_table(file_path: str) -> pd.DataFrame:
    path = Path(file_path)

    if path.suffix.lower() in [".xlsx", ".xls"]:
        return pd.read_excel(path, dtype=str)

    if path.suffix.lower() == ".csv":
        return pd.read_csv(path, dtype=str)

    raise RuntimeError("Поддерживаются только .xlsx, .xls, .csv")


def chunked(items: list, size: int) -> list[list]:
    return [items[i:i + size] for i in range(0, len(items), size)]


def build_payload_items(source_products: list, model_field: str) -> list[dict]:
    payload_items = []

    for source_product in source_products:
        article = clean_value(getattr(source_product, model_field))
        brand = clean_value(source_product.source_brand)

        if not article:
            continue

        payload_items.append(
            {
                "source_product": source_product,
                "article": article,
                "brand": brand,
                "payload": {
                    "article": article,
                    "brand": brand,
                },
            }
        )

    return payload_items


def get_article_candidates(source_product) -> list[tuple[str, str]]:
    candidates = [
        ("article", clean_value(source_product.article)),
        ("manufacturer_article", clean_value(source_product.manufacturer_article)),
        ("factory_article", clean_value(source_product.factory_article)),
    ]

    result = []
    seen = set()

    for matched_by, article in candidates:
        if not article:
            continue

        if article in seen:
            continue

        seen.add(article)
        result.append((matched_by, article))

    return result


def normalize_text(value) -> str:
    return clean_value(value).lower().replace(" ", "")


def choose_best_offer(items: list[dict], *, article: str, brand: str) -> dict | None:
    if not items:
        return None

    article_norm = normalize_text(article)
    brand_norm = normalize_text(brand)

    exact_article = [
        item for item in items
        if normalize_text(item.get("article")) == article_norm
    ]

    if brand_norm:
        exact_brand = [
            item for item in exact_article
            if normalize_text(item.get("brand")) == brand_norm
        ]
        if exact_brand:
            return sorted(
                exact_brand,
                key=lambda x: int(x.get("quantity") or 0),
                reverse=True,
            )[0]

    if exact_article:
        return sorted(
            exact_article,
            key=lambda x: int(x.get("quantity") or 0),
            reverse=True,
        )[0]

    return sorted(
        items,
        key=lambda x: int(x.get("quantity") or 0),
        reverse=True,
    )[0]


class ImportProductsService:
    def __init__(self, batch_size: int = 100) -> None:
        if batch_size > 100:
            raise ValueError("Autoopt batch_size не может быть больше 100")
        self.batch_size = batch_size

    async def run(self, *, file_path: str, limit: int | None = None) -> dict:
        df = read_table(file_path)

        if limit:
            df = df.head(limit)

        for col in REQUIRED_COLUMNS:
            if col not in df.columns:
                raise RuntimeError(f"В таблице нет колонки: {col}")

        stats = {
            "source_rows": len(df),
            "api_requests": 0,
            "found": 0,
            "not_found": 0,
            "failed": 0,
        }

        token = settings.autoalliance_api_key
        if not token:
            raise RuntimeError("AUTOALLIANCE_API_KEY не найден в .env")

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        with SessionLocal() as db:
            repo = AutoAllianceRepository(db)

            source_products = []
            for _, row in tqdm(df.iterrows(), total=len(df), desc="Сохранение строк таблицы"):
                row_dict = {col: clean_value(row.get(col)) for col in df.columns}
                source_product = repo.upsert_source_product_from_row(row_dict)
                source_products.append(source_product)

            db.commit()

            async with httpx.AsyncClient(
                base_url=settings.autoalliance_base_url,
                headers=headers,
                timeout=settings.autoalliance_timeout,
            ) as http_client:
                client = AutoAllianceClient(http_client)

                unresolved = source_products
                resolved_ids = set()

                for matched_by in ["article", "manufacturer_article", "factory_article"]:
                    current_batch_items = []

                    for source_product in unresolved:
                        article = clean_value(getattr(source_product, matched_by))
                        brand = clean_value(source_product.source_brand)

                        if not article:
                            continue

                        current_batch_items.append(
                            {
                                "source_product": source_product,
                                "article": article,
                                "brand": brand,
                                "payload": {
                                    "article": article,
                                    "brand": brand,
                                },
                            }
                        )

                    next_unresolved_ids = {p.id for p in unresolved}

                    batches = chunked(current_batch_items, self.batch_size)

                    for batch in tqdm(batches, desc=f"Autoopt batch: {matched_by}", unit="req"):
                        payload = [item["payload"] for item in batch]

                        try:
                            response_items = await client.search_parts_batch(payload, analogs=True)
                            stats["api_requests"] += 1
                        except Exception as exc:
                            stats["failed"] += len(batch)

                            for item in batch:
                                if item["source_product"].id in resolved_ids:
                                    continue

                                repo.save_not_found(
                                    source_product=item["source_product"],
                                    matched_by=matched_by,
                                    search_article=item["article"],
                                    search_brand=item["brand"],
                                    error_message=str(exc),
                                )
                                resolved_ids.add(item["source_product"].id)

                            db.commit()
                            continue

                        response_by_key = {
                            (
                                clean_value(resp.get("article")),
                                clean_value(resp.get("brand")),
                            ): resp
                            for resp in response_items
                        }

                        for item in batch:
                            source_product = item["source_product"]

                            if source_product.id in resolved_ids:
                                continue

                            key = (item["article"], item["brand"])
                            resp = response_by_key.get(key)

                            if not resp:
                                continue

                            offer = resp.get("offer")

                            if offer:
                                repo.save_found_product(
                                    source_product=source_product,
                                    matched_by=matched_by,
                                    search_article=item["article"],
                                    search_brand=item["brand"],
                                    response_item=resp,
                                )

                                stats["found"] += 1
                                resolved_ids.add(source_product.id)
                                next_unresolved_ids.discard(source_product.id)

                        db.commit()

                    unresolved = [p for p in unresolved if p.id not in resolved_ids]
                    
                    
                fallback_unresolved = []
                for source_product in tqdm(unresolved, desc="Fallback: поиск без бренда"):
                    found = False

                    candidates = [
                        ("article_without_brand", clean_value(source_product.article)),
                        ("manufacturer_article_without_brand", clean_value(source_product.manufacturer_article)),
                        ("factory_article_without_brand", clean_value(source_product.factory_article)),
                    ]

                    seen = set()

                    for matched_by, article in candidates:
                        if not article:
                            continue

                        if article in seen:
                            continue

                        seen.add(article)

                        try:
                            items = await client.search_parts_by_article(article)
                            stats["api_requests"] += 1
                        except Exception as exc:
                            log.exception("Fallback failed article=%s: %s", article, exc)
                            continue

                        offer = choose_best_offer(
                            items,
                            article=article,
                            brand=clean_value(source_product.source_brand),
                        )

                        if offer:
                            repo.save_found_product(
                                source_product=source_product,
                                matched_by=matched_by,
                                search_article=article,
                                search_brand="",
                                response_item={
                                    "article": article,
                                    "brand": clean_value(source_product.source_brand),
                                    "offer": offer,
                                    "analogs": [],
                                },
                            )

                            stats["found"] += 1
                            found = True
                            break

                        await asyncio.sleep(0.1)

                    if not found:
                        fallback_unresolved.append(source_product)

                    db.commit()
                unresolved = fallback_unresolved


                for source_product in tqdm(unresolved, desc="Фиксация not_found"):
                    if source_product.id in resolved_ids:
                        continue

                    candidates = get_article_candidates(source_product)
                    first_article = candidates[0][1] if candidates else ""

                    repo.save_not_found(
                        source_product=source_product,
                        matched_by="all_steps",
                        search_article=first_article,
                        search_brand=clean_value(source_product.source_brand),
                        error_message="Not found by article/manufacturer_article/factory_article",
                    )

                    stats["not_found"] += 1
                    resolved_ids.add(source_product.id)

                db.commit()

        return stats