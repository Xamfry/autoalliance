from pydantic import BaseModel
from typing import List

from src.ozon.schemas.posting_response import Product as PostingProduct


class Product(BaseModel):
    product_id: int
    quantity: int


class Posting(BaseModel):
    products: List[Product]


class PostingSplitRequest(BaseModel):
    posting_number: str
    postings: List[Posting]


    @classmethod
    def from_posting_products(
        cls, posting_number, posting_response_products: list[PostingProduct]
    ):
        postings = []

        for posting_response_product in posting_response_products:
            product = Product(
                product_id=posting_response_product.sku,
                quantity=posting_response_product.quantity,
            )
            posting = Posting(products=[product])
            postings.append(posting)

        return cls(posting_number=posting_number, postings=postings)
