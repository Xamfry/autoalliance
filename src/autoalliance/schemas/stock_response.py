from typing import List, Optional
from pydantic import BaseModel, RootModel


class WarehouseItem(BaseModel):
    id: int
    name: str
    quantity: int


class CatalogProperties(BaseModel):
    group: Optional[str] = None
    subgroup: Optional[str] = None


class Properties(BaseModel):
    tnved: Optional[str] = None
    description: Optional[str] = None
    pictures: List[str]
    pictures_without_watermark: List[str]
    site_url: str
    width: float
    height: float
    length: float
    weight: float
    catalog: Optional[CatalogProperties] = None
    barcode: Optional[str] = None


class OfferItem(BaseModel):
    name: str
    code: str
    article: str
    price: float
    quantity: int
    warehouses: List[WarehouseItem]


    def get_warehouse_qty(self, warehouse_name: str) -> int:
        names = {
            "Рябиновая": "Москва, Рябиновая ул.",
            "Машково": "Машково д., Люберецкий р-н",
        }
        warehouse_name = names[warehouse_name]

        for warehouse in self.warehouses:
            if warehouse.name == warehouse_name:
                return warehouse.quantity
        return 0


class OfferResponse(RootModel):
    root: List[OfferItem]


    def first_item_or_none(self) -> Optional[OfferItem]:
        if self.root:
            return self.root[0]
