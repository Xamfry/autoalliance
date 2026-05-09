from dataclasses import dataclass

from src.autoalliance.client import AutoAllianceApiClient
from src.autoalliance.product_card import ProductCard
from src.autoalliance.parser.mapper import SearchCandidate


@dataclass(slots=True)
class SearchResult:
    candidate: SearchCandidate
    product: ProductCard | None
    error_message: str | None = None


class AutoAllianceService:
    def __init__(self, client: AutoAllianceApiClient) -> None:
        self.client = client

    async def fetch_product(self, candidate: SearchCandidate) -> SearchResult:
        try:
            product = await self.client.get_product_info(candidate.value)
            if product is None:
                return SearchResult(candidate=candidate, product=None, error_message="Product not found")
            return SearchResult(candidate=candidate, product=product)
        except Exception as exc:  # noqa: BLE001
            return SearchResult(candidate=candidate, product=None, error_message=str(exc))

    async def fetch_product_with_fallback(self, candidates: list[SearchCandidate]) -> SearchResult:
        last_result: SearchResult | None = None
        for candidate in candidates:
            result = await self.fetch_product(candidate)
            if result.product is not None:
                return result
            last_result = result
        return last_result or SearchResult(
            candidate=SearchCandidate(field_name="unknown", value=""),
            product=None,
            error_message="No search candidates",
        )
