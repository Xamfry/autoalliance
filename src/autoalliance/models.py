from datetime import datetime
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.app.db import Base


class SourceProduct(Base):
    __tablename__ = "source_products"
    __table_args__ = (
        UniqueConstraint("source_code", name="uq_source_products_source_code"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_code: Mapped[str | None] = mapped_column(String(255), index=True)
    article: Mapped[str | None] = mapped_column(String(255), index=True)
    manufacturer_article: Mapped[str | None] = mapped_column(String(255), index=True)
    factory_article: Mapped[str | None] = mapped_column(String(255), index=True)
    source_name: Mapped[str | None] = mapped_column(String(1000))
    source_brand: Mapped[str | None] = mapped_column(String(255), index=True)
    opt4_price: Mapped[float | None] = mapped_column(Float)
    opt3_price: Mapped[float | None] = mapped_column(Float)
    opt2_price: Mapped[float | None] = mapped_column(Float)
    opt1_price: Mapped[float | None] = mapped_column(Float)
    retail_price: Mapped[float | None] = mapped_column(Float)
    stock_mashkovo: Mapped[int | None] = mapped_column(Integer)
    stock_ketcherskaya: Mapped[int | None] = mapped_column(Integer)
    stock_other: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
    parsed_products: Mapped[list["AutoAllianceProduct"]] = relationship(back_populates="source_product")


class AutoAllianceProduct(Base):
    __tablename__ = "autoalliance_products"
    __table_args__ = (
        UniqueConstraint("source_product_id", "supplier_code", name="uq_autoalliance_source_supplier_code"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_product_id: Mapped[int] = mapped_column(ForeignKey("source_products.id"), index=True)
    parse_status: Mapped[str] = mapped_column(String(50), index=True, default="found")
    matched_by: Mapped[str | None] = mapped_column(String(100), index=True)
    search_article: Mapped[str | None] = mapped_column(String(255), index=True)
    search_brand: Mapped[str | None] = mapped_column(String(255), index=True)
    error_message: Mapped[str | None] = mapped_column(Text)
    supplier_code: Mapped[str | None] = mapped_column(String(255), index=True)
    supplier_article: Mapped[str | None] = mapped_column(String(255), index=True)
    supplier_brand: Mapped[str | None] = mapped_column(String(255), index=True)
    supplier_name: Mapped[str | None] = mapped_column(String(1000))
    price: Mapped[float | None] = mapped_column(Float)
    quantity: Mapped[int | None] = mapped_column(Integer)
    for_order: Mapped[bool | None] = mapped_column(Boolean)
    can_return: Mapped[bool | None] = mapped_column(Boolean)
    tnved: Mapped[str | None] = mapped_column(String(100))
    description_html: Mapped[str | None] = mapped_column(Text)
    description_text: Mapped[str | None] = mapped_column(Text)
    catalog_group: Mapped[str | None] = mapped_column(String(500), index=True)
    catalog_subgroup: Mapped[str | None] = mapped_column(String(500), index=True)
    manual_category: Mapped[str | None] = mapped_column(String(500), index=True)
    manual_subcategory: Mapped[str | None] = mapped_column(String(500), index=True)
    width: Mapped[float | None] = mapped_column(Float)
    height: Mapped[float | None] = mapped_column(Float)
    length: Mapped[float | None] = mapped_column(Float)
    weight: Mapped[float | None] = mapped_column(Float)
    barcode: Mapped[str | None] = mapped_column(String(255), index=True)
    site_url: Mapped[str | None] = mapped_column(String(1500))
    first_picture_url: Mapped[str | None] = mapped_column(String(1500))
    pictures_json: Mapped[list | None] = mapped_column(JSON)
    pictures_without_watermark_json: Mapped[list | None] = mapped_column(JSON)
    warehouses_json: Mapped[list | None] = mapped_column(JSON)
    analogs_json: Mapped[list | None] = mapped_column(JSON)
    preview_applicabilities_json: Mapped[list | None] = mapped_column(JSON)
    preview_certificates_json: Mapped[list | None] = mapped_column(JSON)
    preview_width: Mapped[float | None] = mapped_column(Float)
    preview_height: Mapped[float | None] = mapped_column(Float)
    preview_length: Mapped[float | None] = mapped_column(Float)
    preview_weight: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
    source_product: Mapped[SourceProduct] = relationship(back_populates="parsed_products")
    

class AutoAlliancePurchase(Base):
    __tablename__ = "autoalliance_purchases"
    __table_args__ = (
        UniqueConstraint(
            "posting_number",
            "offer_id",
            "supplier_code",
            "purchase_index",
            name="uq_autoalliance_purchase_unit",
        ),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    shop_id: Mapped[int | None] = mapped_column(Integer, index=True)
    posting_number: Mapped[str] = mapped_column(String(255), index=True)
    offer_id: Mapped[str | None] = mapped_column(String(255), index=True)
    sku: Mapped[int | None] = mapped_column(Integer, index=True)
    supplier_code: Mapped[str] = mapped_column(String(255), index=True)
    purchase_index: Mapped[int] = mapped_column(Integer, default=1)
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(50), default="new", index=True)
    autoalliance_order_id: Mapped[str | None] = mapped_column(String(255), index=True)
    response_json: Mapped[dict | None] = mapped_column(JSON)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
    )
