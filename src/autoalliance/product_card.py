from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class ProductCard:
    good_id: int | None = None
    name: str | None = None
    url: str | None = None
    order_code: str | None = None
    article: str | None = None
    articles: list[str] = field(default_factory=list)
    brand_short_name: str | None = None
    brand_full_name: str | None = None
    description: str | None = None
    images: list[str] = field(default_factory=list)
    certificates: list[str] = field(default_factory=list)
    analog_codes: list[str] = field(default_factory=list)
    characteristics: dict[str, Any] = field(default_factory=dict)
    category_paths: list[str] = field(default_factory=list)
