from dataclasses import dataclass

from src.autoalliance.parser.validators import normalize_text


@dataclass(slots=True)
class SearchCandidate:
    field_name: str
    value: str


@dataclass(slots=True)
class SourceRow:
    source_code: str | None
    article: str | None
    manufacturer_article: str | None
    factory_article: str | None
    source_name: str | None
    source_brand: str | None
    opt4_price: str | None
    opt3_price: str | None
    opt2_price: str | None
    opt1_price: str | None
    retail_price: str | None
    stock_mashkovo: str | None
    stock_ketcherskaya: str | None
    stock_other: str | None

    def build_candidates(self) -> list[SearchCandidate]:
        ordered = [
            SearchCandidate(field_name="article", value=self.article or ""),
            SearchCandidate(field_name="manufacturer_article", value=self.manufacturer_article or ""),
            SearchCandidate(field_name="factory_article", value=self.factory_article or ""),
        ]
        seen: set[str] = set()
        result: list[SearchCandidate] = []
        for item in ordered:
            value = normalize_text(item.value)
            if not value or value in seen:
                continue
            seen.add(value)
            result.append(SearchCandidate(field_name=item.field_name, value=value))
        return result


def map_dataframe_row(row: dict) -> SourceRow:
    return SourceRow(
        source_code=normalize_text(row.get("Код товара")),
        article=normalize_text(row.get("Артикул")),
        manufacturer_article=normalize_text(row.get("Артикул производителя")),
        factory_article=normalize_text(row.get("Артикул завода")),
        source_name=normalize_text(row.get("Наименование товара")),
        source_brand=normalize_text(row.get("Производитель")),
        opt4_price=normalize_text(row.get("ОПТ4")),
        opt3_price=normalize_text(row.get("ОПТ3")),
        opt2_price=normalize_text(row.get("ОПТ2")),
        opt1_price=normalize_text(row.get("ОПТ1")),
        retail_price=normalize_text(row.get("Розница")),
        stock_mashkovo=normalize_text(row.get("Остаток Машково")),
        stock_ketcherskaya=normalize_text(row.get("Остаток Кетчерская")),
        stock_other=normalize_text(row.get("Остаток Прочие")),
    )
