from typing import Any, Dict, List
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from pydantic import BaseModel, computed_field

from src.autoalliance.product_card import ProductCard


BASE_URL = "https://autoopt.ru/"


class ProductCharacteristicsResponse(BaseModel):
    response: Dict[str, Any]


    @computed_field
    @property
    def data(self) -> Dict[str, Any]:
        """Извлечение данных о товаре из ответа."""
        return self.response.get("good", {})


    @property
    def good_id(self) -> int | None:
        """ID товара."""
        return self.data.get("id")


    @property
    def name(self) -> str | None:
        """Название товара."""
        return self.data.get("title")


    @property
    def url(self) -> str | None:
        """URL товара."""
        if path := self.data.get("url"):
            catalog_url = urljoin(BASE_URL, "/catalog/")

            return urljoin(catalog_url, path)
        return None


    @property
    def order_code(self) -> str | None:
        """Код для заказа."""
        return self.data.get("code")


    @property
    def article(self) -> str | None:
        """Артикул товара."""
        if article := self.data.get("article"):
            return str(article)
        return None


    @property
    def articles(self) -> str | None:
        """Дополнительные артикулы в виде строки."""
        return self.data.get("articles") or None


    @property
    def brand_short_name(self) -> str | None:
        """Короткое название бренда (например, "РТР")."""
        short_name = self.data.get("brand", {}).get("name")
        if short_name is None:
            return

        if short_name.lower() in ["не указан", "нет"]:
            return None

        return short_name


    @property
    def brand_full_name(self) -> str | None:
        """Полное торговое наименование бренда (например, "РезиноТехнический Ресурс")."""
        return self.data.get("brand", {}).get("tradeMarkName") or None


    @property
    def description(self) -> str | None:
        """Описание товара."""
        description_html = self.data.get("description")
        if description_html is None:
            return None
        soup = BeautifulSoup(description_html, "html.parser")
        return soup.get_text(separator=" ", strip=True)


    @property
    def images(self) -> List[str]:
        """Список URL изображений товара."""
        image_paths = self.data.get("big_pictures", [])
        return [urljoin(BASE_URL, path) for path in image_paths]


    @property
    def certificates(self) -> List[str]:
        """Список URL сертификатов."""
        cert_list = self.data.get("certificates", [])
        return [urljoin(BASE_URL, cert["url"]) for cert in cert_list if "url" in cert]


    @property
    def analog_codes(self) -> List[str]:
        """Список кодов аналогов."""
        analogs_list = self.response.get("analogs", [])
        return [analog["code"] for analog in analogs_list if "code" in analog]


    @property
    def characteristics(self) -> Dict[str, Any]:
        """Объединенный словарь характеристик товара."""
        main_properties = self.data.get("main_properties", [])
        properties = self.data.get("properties", [])
        combined = main_properties + properties
        return {
            prop["name"]: prop["value"]
            for prop in combined
            if "name" in prop and "value" in prop
        }


    @property
    def category_paths(self) -> List[str]:
        """Список полных путей категорий."""
        sections = self.data.get("sections")
        if not sections:
            return []

        sections_by_id = {int(k): v for k, v in sections.items()}
        leaf_nodes = [
            node for node in sections_by_id.values() if not node.get("parent")
        ]

        all_paths = []
        for leaf in leaf_nodes:
            path_parts = [leaf["name"]]
            parent_id = leaf.get("parentId")
            while parent_id and parent_id in sections_by_id:
                parent_node = sections_by_id[parent_id]
                path_parts.insert(0, parent_node["name"])
                parent_id = parent_node.get("parentId")
            all_paths.append(" / ".join(path_parts))

        return all_paths


    def to_domain(self) -> ProductCard:
        """Конвертирует схему в доменную модель ProductCard."""
        return ProductCard(
            good_id=self.good_id,
            name=self.name,
            url=self.url,
            order_code=self.order_code,
            article=self.article,
            articles=self.articles,
            brand_short_name=self.brand_short_name,
            brand_full_name=self.brand_full_name,
            description=self.description,
            images=self.images,
            certificates=self.certificates,
            analog_codes=self.analog_codes,
            characteristics=self.characteristics,
            category_paths=self.category_paths,
        )
