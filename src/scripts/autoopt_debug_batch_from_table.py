import argparse
import asyncio
import json
import os
from pathlib import Path

import httpx
import pandas as pd
from dotenv import load_dotenv


ARTICLE_COLUMNS = [
    "Артикул",
    "Артикул производителя",
    "Артикул завода",
]

BRAND_COLUMN = "Производитель"


def clean_value(value) -> str:
    if value is None:
        return ""

    value = str(value).strip()

    if value.lower() in {"nan", "none", "null"}:
        return ""

    return value


def chunked(items: list, size: int) -> list[list]:
    return [items[i:i + size] for i in range(0, len(items), size)]


def build_requests(df: pd.DataFrame, article_column: str) -> list[dict]:
    requests = []

    for row_index, row in df.iterrows():
        article = clean_value(row.get(article_column))
        brand = clean_value(row.get(BRAND_COLUMN))

        if not article:
            continue

        requests.append(
            {
                "row_index": int(row_index),
                "article_column": article_column,
                "article": article,
                "brand": brand,
                "payload": {
                    "article": article,
                    "brand": brand,
                },
            }
        )

    return requests


def extract_products(data) -> list[dict]:
    if isinstance(data, list):
        return data

    if isinstance(data, dict):
        for key in ["items", "result", "data", "parts"]:
            value = data.get(key)
            if isinstance(value, list):
                return value

    return []


def has_category(product: dict) -> bool:
    properties = product.get("properties") or {}
    catalog = properties.get("catalog") or {}

    return bool(catalog.get("group") or catalog.get("subgroup"))


async def request_batch(
    client: httpx.AsyncClient,
    payload: list[dict],
) -> list[dict]:
    response = await client.post(
        "/api/v2/parts/search/batch",
        params={"analogs": 1},
        json=payload,
    )

    print("HTTP:", response.status_code)

    response.raise_for_status()
    return response.json()


async def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser()
    parser.add_argument("file_path", help="Путь к xlsx/xls/csv файлу")
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--article-column", default="Артикул")
    parser.add_argument("--batch-size", type=int, default=100)

    args = parser.parse_args()

    token = os.getenv("AUTOALLIANCE_API_KEY")
    base_url = os.getenv("AUTOALLIANCE_BASE_URL", "https://beta.autoopt.ru").rstrip("/")

    if not token:
        raise RuntimeError("AUTOALLIANCE_API_KEY не найден в .env")

    if args.batch_size > 100:
        raise RuntimeError("Autoopt batch принимает максимум 100 товаров за запрос")

    file_path = Path(args.file_path)

    if file_path.suffix.lower() in [".xlsx", ".xls"]:
        df = pd.read_excel(file_path)
    elif file_path.suffix.lower() == ".csv":
        df = pd.read_csv(file_path)
    else:
        raise RuntimeError("Поддерживаются только .xlsx, .xls, .csv")

    if args.limit:
        df = df.head(args.limit)

    print("Строк прочитано:", len(df))
    print("Колонки:", list(df.columns))

    if args.article_column not in df.columns:
        raise RuntimeError(f"Нет колонки: {args.article_column}")

    if BRAND_COLUMN not in df.columns:
        raise RuntimeError(f"Нет колонки: {BRAND_COLUMN}")

    requests = build_requests(df, args.article_column)
    print("Запросов подготовлено:", len(requests))

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    Path("data/debug").mkdir(parents=True, exist_ok=True)

    all_results = []
    found_count = 0
    category_count = 0
    no_category_count = 0

    async with httpx.AsyncClient(
        base_url=base_url,
        headers=headers,
        timeout=60,
    ) as client:
        for batch_number, batch in enumerate(chunked(requests, args.batch_size), start=1):
            payload = [item["payload"] for item in batch]

            print(f"\nBatch {batch_number}: отправляем {len(payload)} товаров")

            raw_data = await request_batch(client, payload)
            products = extract_products(raw_data)

            print("Найдено товаров:", len(products))

            for product in products:
                found_count += 1

                if has_category(product):
                    category_count += 1
                else:
                    no_category_count += 1

            all_results.append(
                {
                    "batch_number": batch_number,
                    "sent": batch,
                    "raw_response": raw_data,
                    "products_count": len(products),
                }
            )

    out_path = Path(
        f"data/debug/autoopt_batch_{args.article_column}_{len(requests)}.json"
        .replace(" ", "_")
        .replace("/", "_")
        .replace("\\", "_")
    )

    with out_path.open("w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)

    print("\n=== ИТОГ ===")
    print("Отправлено:", len(requests))
    print("Найдено товаров:", found_count)
    print("С категорией:", category_count)
    print("Без категории:", no_category_count)
    print("JSON сохранён:", out_path)


if __name__ == "__main__":
    asyncio.run(main())