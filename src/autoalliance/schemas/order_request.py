import json
import logging
from typing import List, Optional

from pydantic import BaseModel


class Item(BaseModel):
    code: str
    quantity: int


class OrderRequest(BaseModel):
    profile_id: Optional[int] = None
    comment: Optional[str] = None
    items: List[Item]

    @classmethod
    def new_request(cls, order_codes: list[str]):
        items = [Item(code=order_code, quantity=1) for order_code in order_codes]

        return cls(
            profile_id=None,
            items=items,
        )

    def add_order(self, order_code: str, quantity):
        item = Item(code=order_code, quantity=quantity)
        self.items.append(item)

    def log(self):
        payload = self.model_dump(exclude_none=False)

        logging.info(
            "OrderRequest JSON:\n%s",
            json.dumps(payload, indent=4, ensure_ascii=False),
        )
