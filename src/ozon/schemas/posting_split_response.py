from pydantic import BaseModel
from typing import List


class Product(BaseModel):
    product_id: int
    quantity: int


class Posting(BaseModel):
    posting_number: str
    products: List[Product]


class PostingSplitResponse(BaseModel):
    parent_posting: Posting
    postings: List[Posting]
