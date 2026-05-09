import datetime
from typing import Any, List, Optional, Literal
from pydantic import BaseModel, Field


class DeliveryMethod(BaseModel):
    id: int
    name: str
    warehouse_id: int
    warehouse: str
    tpl_provider_id: int
    tpl_provider: str


class OptionalPosting(BaseModel):
    products_with_possible_mandatory_mark: List[int]


class Cancellation(BaseModel):
    cancel_reason_id: int
    cancel_reason: str
    cancellation_type: str
    cancelled_after_ship: bool
    affect_cancellation_rating: bool
    cancellation_initiator: str


class Product(BaseModel):
    price: str
    currency_code: str
    is_blr_traceable: bool
    is_marketplace_buyout: bool
    offer_id: str
    name: str
    sku: int
    quantity: int
    imei: List


class LegalInfo(BaseModel):
    company_name: str
    inn: str
    kpp: str


class Requirements(BaseModel):
    products_requiring_change_country: List
    products_requiring_gtd: List
    products_requiring_country: List
    products_requiring_mandatory_mark: List
    products_requiring_jw_uin: List
    products_requiring_imei: List
    products_requiring_rnpt: List
    products_requiring_weight: List


class Tariffication(BaseModel):
    current_tariff_rate: float
    current_tariff_type: str
    current_tariff_charge: str
    current_tariff_charge_currency_code: str
    next_tariff_rate: float
    next_tariff_type: str
    next_tariff_charge: str
    next_tariff_starts_at: Optional[datetime.datetime] = None
    next_tariff_charge_currency_code: str


class FinancialDataProduct(BaseModel):
    commission_amount: float
    commission_percent: float
    payout: float
    product_id: int
    old_price: float
    price: float
    total_discount_value: float
    total_discount_percent: float
    actions: List[str]
    quantity: int
    currency_code: str
    customer_currency_code: str
    customer_price: float


class FinancialData(BaseModel):
    products: List[FinancialDataProduct]
    cluster_from: str
    cluster_to: str


class AnalyticsData(BaseModel):
    region: Optional[str] = None
    city: Optional[str] = None
    delivery_type: Optional[str] = None
    is_premium: Optional[bool] = None
    payment_type_group_name: Optional[str] = None
    warehouse_id: Optional[int] = None
    warehouse: Optional[str] = None
    tpl_provider_id: Optional[int] = None
    tpl_provider: Optional[str] = None
    delivery_date_begin: Optional[datetime.datetime] = None
    delivery_date_end: Optional[datetime.datetime] = None
    is_legal: Optional[bool] = None
    client_delivery_date_begin: Optional[datetime.datetime] = None
    client_delivery_date_end: Optional[datetime.datetime] = None


class Posting(BaseModel):
    posting_number: str
    order_id: int
    order_number: str
    pickup_code_verified_at: Optional[datetime.datetime] = None
    status: Literal[
        "acceptance_in_progress",  # идёт приёмка
        "arbitration",  # арбитраж
        "awaiting_approve",  # ожидает подтверждения
        "awaiting_deliver",  # ожидает отгрузки
        "awaiting_packaging",  # ожидает упаковки
        "awaiting_registration",  # ожидает регистрации
        "awaiting_verification",  # создано
        "cancelled",  # отменено
        "cancelled_from_split_pending",  # отменён из-за разделения отправления
        "client_arbitration",  # клиентский арбитраж доставки
        "delivering",  # доставляется
        "driver_pickup",  # у водителя
        "not_accepted",  # не принят на сортировочном центре
        "delivered",  # доставлен
    ]
    substatus: str
    delivery_method: Optional[DeliveryMethod] = None
    tracking_number: str
    tpl_integration_type: str
    in_process_at: datetime.datetime
    shipment_date: datetime.datetime
    shipment_date_without_delay: datetime.datetime
    delivering_date: Optional[datetime.datetime] = None
    optional: Optional[OptionalPosting] = None
    cancellation: Cancellation
    customer: Optional[Any] = None
    products: List[Product] = []
    addressee: Optional[Any] = None
    barcodes: Optional[Any] = None
    analytics_data: Optional[AnalyticsData] = None
    financial_data: Optional[FinancialData] = None
    is_express: bool
    legal_info: Optional[LegalInfo] = None
    quantum_id: Optional[int] = None
    requirements: Optional[Requirements] = None
    tariffication: Optional[Tariffication] = None


    def need_set_country(self):
        if not self.requirements:
            return False

        return bool(self.requirements.products_requiring_country)


    def get_first_offer_id(self):
        return self.products[0].offer_id


    def get_split_products(self) -> list[Product]:
        products = []
        for product in self.products:
            if product.quantity == 1:
                products.append(product)
                continue

            for _ in range(product.quantity):
                one_product = Product.model_validate(product, from_attributes=True)
                one_product.quantity = 1
                products.append(one_product)

        return products


class Result(BaseModel):
    postings: List[Posting]
    has_next: bool


class PostingResponse(BaseModel):
    result: Result


    @classmethod
    def empty_instance(cls):
        return cls(result=Result(postings=[], has_next=False))


    def merge_other_response(self, posting_response: "PostingResponse"):
        self.result.postings.extend(posting_response.result.postings)
        self.result.has_next = self.result.has_next or posting_response.result.has_next


    def get_all_postings(self):
        return self.result.postings


    def get_all_possible_postings(self) -> list[Posting]:
        """Все доставки которые могут быть завершены"""
        impossible_postings = [
            "arbitration",  # арбитраж
            "awaiting_approve",  # ожидает подтверждения
            "cancelled",  # отменено
            "cancelled_from_split_pending",  # отменён из-за разделения отправления
            "client_arbitration",  # клиентский арбитраж доставки
            "not_accepted",  # не принят на сортировочном центре
        ]
        return [
            posting
            for posting in self.result.postings
            if posting.status not in impossible_postings
        ]


    def get_new_postings(self) -> list[Posting]:
        """Все новые доставки"""
        return [
            posting
            for posting in self.result.postings
            if posting.status in ["awaiting_packaging"]
        ]


    def get_new_grouped_postings(self):
        """Возвращает отправления в которых более одного товара"""
        return [
            posting
            for posting in self.get_new_postings()
            if not self._is_single_posting(posting)
        ]


    def get_single_postings(self):
        return [
            posting
            for posting in self.get_all_postings()
            if self._is_single_posting(posting)
        ]


    def _is_single_posting(self, posting: Posting):
        if len(posting.products) == 1 and posting.products[0].quantity == 1:
            return True
        return False


    def get_possible_financial_data_products(self) -> list[FinancialDataProduct]:
        """Все продукты которые еще могут быть доставлены"""
        postings = self.get_all_possible_postings()
        products = []
        for posting in postings:
            if posting.financial_data is None:
                continue
            products.extend(posting.financial_data.products)
        return products


    def get_possible_products(self) -> list[Product]:
        """Все продукты которые еще могут быть доставлены"""
        postings = self.get_all_possible_postings()
        products = []
        for posting in postings:
            products.extend(posting.products)
        return products


    def get_offer_id_by_sku(self, sku):
        for posting in self.result.postings:
            for product in posting.products:
                if product.sku == sku:
                    return product.offer_id
