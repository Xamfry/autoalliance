import argparse
import asyncio
import json
import os
from pathlib import Path

import httpx
from dotenv import load_dotenv


def print_product(item: dict) -> None:
    print("\n=== ОСНОВНЫЕ ПОЛЯ ===")
    print("name:", item.get("name"))
    print("code:", item.get("code"))
    print("article:", item.get("article"))
    print("brand:", item.get("brand"))
    print("price:", item.get("price"))
    print("quantity:", item.get("quantity"))
    print("for_order:", item.get("for_order"))
    print("can_return:", item.get("can_return"))

    properties = item.get("properties") or {}

    print("\n=== PROPERTIES ===")
    print("tnved:", properties.get("tnved"))
    print("description:", properties.get("description"))
    print("site_url:", properties.get("site_url"))
    print("width:", properties.get("width"))
    print("height:", properties.get("height"))
    print("length:", properties.get("length"))
    print("weight:", properties.get("weight"))

    catalog = properties.get("catalog") or {}

    print("\n=== КАТЕГОРИИ ===")
    print("catalog:", catalog)
    print("group:", catalog.get("group"))
    print("subgroup:", catalog.get("subgroup"))

    print("\n=== КАРТИНКИ ===")
    print("pictures:", properties.get("pictures"))
    print("pictures_without_watermark:", properties.get("pictures_without_watermark"))

    print("\n=== СКЛАДЫ ===")
    for wh in item.get("warehouses") or []:
        print(wh)


async def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser()
    parser.add_argument("--article", required=True, help="Артикул товара")
    parser.add_argument("--brand", default=None, help="Бренд товара")
    parser.add_argument("--method", choices=["batch", "article", "article-brand"], default="article")
    args = parser.parse_args()

    token = os.getenv("AUTOALLIANCE_API_KEY")
    base_url = os.getenv("AUTOALLIANCE_BASE_URL", "https://beta.autoopt.ru").rstrip("/")

    if not token:
        raise RuntimeError("AUTOALLIANCE_API_KEY не найден в .env")

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    async with httpx.AsyncClient(base_url=base_url, headers=headers, timeout=30) as client:
        if args.method == "batch":
            payload = [
                {
                    "article": args.article,
                    "brand": args.brand or "",
                }
            ]

            response = await client.post(
                "/api/v2/parts/search/batch",
                params={"analogs": 1},
                json=payload,
            )

        elif args.method == "article-brand":
            if not args.brand:
                raise RuntimeError("Для article-brand нужен --brand")

            response = await client.get(
                f"/api/v2/parts/search/article-brand/{args.article}",
                params={"brand": args.brand},
            )

        else:
            response = await client.get(
                f"/api/v2/parts/search/{args.article}",
            )

        print("HTTP:", response.status_code)
        response.raise_for_status()

        data = response.json()

    Path("data/debug").mkdir(parents=True, exist_ok=True)

    safe_article = args.article.replace("/", "_").replace("\\", "_")
    out_path = Path(f"data/debug/autoopt_{args.method}_{safe_article}.json")

    with out_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"\nJSON сохранён: {out_path}")

    print("\n=== ТИП ОТВЕТА ===")
    print(type(data).__name__)

    if isinstance(data, list):
        print("items:", len(data))

        if data:
            print_product(data[0])

    elif isinstance(data, dict):
        print("keys:", list(data.keys()))

        # если API вернул одиночный товар
        if "name" in data or "article" in data:
            print_product(data)

        # если API вернул обёртку
        for key in ["items", "result", "parts", "data"]:
            value = data.get(key)
            if isinstance(value, list):
                print(f"\nНайден список в ключе {key}: {len(value)}")
                if value:
                    print_product(value[0])
                break

    else:
        print(data)


if __name__ == "__main__":
    asyncio.run(main())

