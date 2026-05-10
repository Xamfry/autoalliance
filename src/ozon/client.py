from __future__ import annotations
import httpx
import asyncio
import base64
from typing import Any

from src.ozon.models import OzonShop
from src.ozon.schemas.posting_request import PostingRequest
from src.ozon.schemas.posting_response import PostingResponse
from src.ozon.schemas.posting_split_request import PostingSplitRequest
from src.ozon.schemas.posting_split_response import PostingSplitResponse


class OzonClient:
    base_url = "https://api-seller.ozon.ru"
    def __init__(self, http_client: httpx.AsyncClient, shop: OzonShop) -> None:
        self.http_client = http_client
        self.shop = shop
        self.headers = {"Client-Id": str(shop.client_id), "Api-Key": str(shop.token), "Content-Type": "application/json"}


    async def _post(self, path: str, payload: dict) -> dict:
        response = await self.http_client.post(f"{self.base_url}{path}", headers=self.headers, json=payload)
        response.raise_for_status()
        return response.json()


    async def get_product_list(self, *, limit: int = 1000, last_id: str = "", visibility: str = "ALL") -> dict:
        return await self._post("/v3/product/list", {"filter": {"visibility": visibility}, "last_id": last_id, "limit": limit})


    async def get_all_product_ids(self, *, visibility: str = "ALL") -> list[int]:
        product_ids: list[int] = []
        last_id = ""
        while True:
            data = await self.get_product_list(limit=1000, last_id=last_id, visibility=visibility)
            result = data.get("result") or {}
            items = result.get("items") or []
            for item in items:
                product_id = item.get("product_id") or item.get("id")
                if product_id is not None:
                    product_ids.append(int(product_id))
            last_id = result.get("last_id") or ""
            if not items or not last_id:
                break
        return product_ids


    async def get_product_info_list(self, product_ids: list[int]) -> list[dict]:
        if not product_ids:
            return []

        payload = {
            "product_id": product_ids,
        }

        data = await self._post("/v3/product/info/list", payload)

        if not isinstance(data, dict):
            return []

        items = data.get("items")
        if isinstance(items, list):
            return items

        result = data.get("result")
        if isinstance(result, dict):
            result_items = result.get("items")
            if isinstance(result_items, list):
                return result_items

        if isinstance(result, list):
            return result

        return []


    async def get_product_info_list_chunks(
        self,
        product_ids: list[int],
        chunk_size: int = 1000,
    ) -> list[dict]:
        result: list[dict] = []

        for i in range(0, len(product_ids), chunk_size):
            chunk = product_ids[i:i + chunk_size]
            items = await self.get_product_info_list(product_ids=chunk)
            result.extend(items)

        return result


    async def get_product_attributes(
        self,
        *,
        product_ids: list[int],
        limit: int = 100,
    ) -> list[dict]:
        if not product_ids:
            return []

        payload = {
            "filter": {
                "product_id": product_ids,
                "visibility": "ALL",
            },
            "limit": limit,
        }

        data = await self._post("/v4/product/info/attributes", payload)

        if isinstance(data, dict):
            result = data.get("result")
            if isinstance(result, list):
                return result

            if isinstance(result, dict):
                items = result.get("items")
                if isinstance(items, list):
                    return items

            items = data.get("items")
            if isinstance(items, list):
                return items

        return []


    async def get_product_attributes_chunks(
        self,
        *,
        product_ids: list[int],
        chunk_size: int = 100,
    ) -> list[dict]:
        result: list[dict] = []

        for i in range(0, len(product_ids), chunk_size):
            chunk = product_ids[i:i + chunk_size]
            items = await self.get_product_attributes(product_ids=chunk, limit=chunk_size)
            result.extend(items)

        return result
    

    async def get_postings(self, postings_request: PostingRequest) -> PostingResponse:
        data = await self._post(
            "/v3/posting/fbs/list",
            postings_request.model_dump(exclude_none=True, by_alias=True),
        )
        return PostingResponse.model_validate(data)


    async def get_all_postings(self, postings_request: PostingRequest) -> PostingResponse:
        offset = postings_request.offset
        limit = postings_request.limit

        merged = PostingResponse.empty_instance()

        while True:
            page_request = postings_request.model_copy(update={"offset": offset})
            page = await self.get_postings(page_request)

            merged.merge_other_response(page)

            if not page.result.postings:
                break

            if not page.result.has_next:
                break

            offset += limit

        return merged


    async def split_posting(
        self,
        posting_split_request: PostingSplitRequest,
    ) -> PostingSplitResponse:
        data = await self._post(
            "/v1/posting/fbs/split",
            posting_split_request.model_dump(),
        )
        return PostingSplitResponse.model_validate(data)
    

    async def get_fbs_package_label_pdf_v2(
        self,
        *,
        posting_numbers: list[str],
    ) -> bytes | None:
        data = await self._post(
            "/v2/posting/fbs/package-label",
            {
                "posting_number": posting_numbers,
            },
        )

        if not isinstance(data, dict):
            return None

        content = (
            data.get("content")
            or data.get("file")
            or data.get("pdf")
            or data.get("result", {}).get("content")
            or data.get("result", {}).get("file")
        )

        if not content:
            return None

        if isinstance(content, str):
            return base64.b64decode(content)

        return None


    async def get_fbs_package_label_pdf_with_wait(
        self,
        *,
        posting_numbers: list[str],
        attempts: int = 6,
        delay_seconds: float = 2.0,
    ) -> bytes:
        last_error: Exception | None = None

        for attempt in range(1, attempts + 1):
            try:
                pdf = await self.get_fbs_package_label_pdf_v2(
                    posting_numbers=posting_numbers,
                )

                if pdf:
                    return pdf

            except Exception as exc:
                last_error = exc

            await asyncio.sleep(delay_seconds)

        raise RuntimeError(
            f"Ozon не отдал стикер после {attempts} попыток. "
            f"posting_numbers={posting_numbers}. "
            f"last_error={last_error}"
        )