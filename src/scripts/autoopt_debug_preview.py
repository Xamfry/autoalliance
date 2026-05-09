import argparse
import asyncio
import json
from pathlib import Path

import httpx


HEADERS = {
    "Accept": "application/json",
    "User-Agent": "Mozilla/5.0",
    "Referer": "https://www.autoopt.ru/",
}


def clean_order_code(value: str) -> str:
    value = str(value).strip()

    if value.endswith(".0"):
        value = value[:-2]

    # Старый фикс из исходников.
    value = value.replace("0.", "")

    return value


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Debug Autoopt product preview API"
    )
    parser.add_argument(
        "order_code",
        help="Код товара Autoopt, например 000003",
    )
    args = parser.parse_args()

    order_code = clean_order_code(args.order_code)

    url = f"https://www.autoopt.ru/api/v1/catalog/preview/{order_code}"

    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.get(url, headers=HEADERS)

    print("URL:", url)
    print("HTTP:", response.status_code)

    if response.status_code == 404:
        print("Товар не найден")
        return

    response.raise_for_status()

    data = response.json()

    Path("data/debug").mkdir(parents=True, exist_ok=True)

    out_path = Path(f"data/debug/autoopt_preview_{order_code}.json")

    with out_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print("JSON сохранён:", out_path)

    if isinstance(data, dict):
        print("Ключи верхнего уровня:", list(data.keys()))

        good = data.get("good")
        if isinstance(good, dict):
            print("\n=== good ===")
            print("id:", good.get("id"))
            print("code:", good.get("code"))
            print("article:", good.get("article"))
            print("title:", good.get("title"))
            print("brand:", good.get("brand"))
            print("path:", good.get("path"))

            print("\nКлючи good:", list(good.keys()))

        analogs = data.get("analogs")
        if isinstance(analogs, list):
            print("\nanalogs:", len(analogs))

        sections = data.get("sections")
        if isinstance(sections, list):
            print("sections:", len(sections))


if __name__ == "__main__":
    asyncio.run(main())