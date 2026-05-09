import asyncio
import logging
from typing import Any
from urllib.parse import urljoin
from bs4 import BeautifulSoup
import httpx

from src.app.config import settings
AUTOOPT_SITE_BASE_URL = "https://www.autoopt.ru"

log = logging.getLogger(__name__)


def clean_order_code(value: str | int) -> str:
    value = str(value).strip()

    if value.endswith(".0"):
        value = value[:-2]

    return value

class AutoAllianceApiError(RuntimeError):
    pass


class AutoAllianceClient:
    def __init__(self, http_client: httpx.AsyncClient) -> None:
        self.http_client = http_client

    async def _get_with_retries(
        self,
        path: str,
        *,
        params: dict | None = None,
        retries: int = 5,
    ) -> Any:
        last_error: Exception | None = None

        for attempt in range(1, retries + 1):
            try:
                response = await self.http_client.get(path, params=params)

                if response.status_code == 429:
                    wait = min(60, attempt * 5)
                    log.warning("Autoopt 429 GET. attempt=%s wait=%s sec", attempt, wait)
                    await asyncio.sleep(wait)
                    continue

                if response.status_code >= 500:
                    wait = min(60, attempt * 3)
                    log.warning("Autoopt GET server error HTTP=%s attempt=%s wait=%s sec", response.status_code, attempt, wait)
                    await asyncio.sleep(wait)
                    continue

                if response.status_code >= 400:
                    raise AutoAllianceApiError(
                        f"HTTP {response.status_code}: {response.text[:500]}"
                    )

                return response.json()

            except (httpx.TimeoutException, httpx.ConnectError, httpx.ReadError) as exc:
                last_error = exc
                wait = min(60, attempt * 3)
                log.warning("Autoopt GET connection error: %s. attempt=%s wait=%s sec", exc, attempt, wait)
                await asyncio.sleep(wait)

        raise AutoAllianceApiError(f"Autoopt GET failed after {retries} retries: {last_error}")


    async def search_parts_by_article(self, article: str) -> list[dict]:
        data = await self._get_with_retries(
            f"/api/v2/parts/search/{article}",
        )

        if isinstance(data, list):
            return data

        return []

    async def _post_with_retries(
        self,
        path: str,
        *,
        json_data: Any,
        params: dict | None = None,
        retries: int = 5,
    ) -> Any:
        last_error: Exception | None = None

        for attempt in range(1, retries + 1):
            try:
                response = await self.http_client.post(
                    path,
                    params=params,
                    json=json_data,
                )

                if response.status_code == 429:
                    wait = min(60, attempt * 5)
                    log.warning("Autoopt 429. attempt=%s wait=%s sec", attempt, wait)
                    await asyncio.sleep(wait)
                    continue

                if response.status_code >= 500:
                    wait = min(60, attempt * 3)
                    log.warning(
                        "Autoopt server error HTTP=%s attempt=%s wait=%s sec",
                        response.status_code,
                        attempt,
                        wait,
                    )
                    await asyncio.sleep(wait)
                    continue

                if response.status_code >= 400:
                    raise AutoAllianceApiError(
                        f"HTTP {response.status_code}: {response.text[:500]}"
                    )

                return response.json()

            except (httpx.TimeoutException, httpx.ConnectError, httpx.ReadError) as exc:
                last_error = exc
                wait = min(60, attempt * 3)
                log.warning("Autoopt connection error: %s. attempt=%s wait=%s sec", exc, attempt, wait)
                await asyncio.sleep(wait)

        raise AutoAllianceApiError(f"Autoopt request failed after {retries} retries: {last_error}")

    async def search_parts_batch(self, items: list[dict], *, analogs: bool = True) -> list[dict]:
        if not items:
            return []

        if len(items) > 100:
            raise ValueError("search_parts_batch принимает максимум 100 товаров")

        data = await self._post_with_retries(
            "/api/v2/parts/search/batch",
            params={"analogs": 1 if analogs else 0},
            json_data=items,
        )

        if isinstance(data, list):
            return data

        return []


    async def get_product_preview(self, order_code: str | int) -> dict | None:
        PREVIEW_HEADERS = {
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://www.autoopt.ru/",
        }
        order_code = clean_order_code(order_code)

        url = f"{AUTOOPT_SITE_BASE_URL}/api/v1/catalog/preview/{order_code}"

        response = await self.http_client.get(
            url,
            headers=PREVIEW_HEADERS,
        )

        if response.status_code == 404:
            return None

        response.raise_for_status()

        data = response.json()

        if isinstance(data, dict):
            return data

        return None
