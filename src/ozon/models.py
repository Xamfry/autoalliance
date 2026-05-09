from datetime import datetime
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text, Column, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.app.db import Base

class OzonShop(Base):
    __tablename__ = "ozon_shops"
    __table_args__ = (UniqueConstraint("shop_name", name="uq_ozon_shop_name"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    shop_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    client_id: Mapped[str] = mapped_column(String(255), nullable=False)
    token: Mapped[str] = mapped_column(Text, nullable=False)
    warehouse: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
    products: Mapped[list["OzonProduct"]] = relationship(back_populates="shop")

class OzonProduct(Base):
    __tablename__ = "ozon_products"
    __table_args__ = (UniqueConstraint("shop_id", "offer_id", name="uq_ozon_product_shop_offer"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    shop_id: Mapped[int] = mapped_column(ForeignKey("ozon_shops.id"), index=True)
    sku: Mapped[int | None] = mapped_column(Integer, index=True)
    name: Mapped[str | None] = mapped_column(String(1000))
    product_id: Mapped[int | None] = mapped_column(Integer, index=True)
    offer_id: Mapped[str] = mapped_column(String(255), index=True)
    price_current: Mapped[float | None] = mapped_column(Float)
    price_calc: Mapped[int | None] = mapped_column(Integer)
    supplier_price_rub: Mapped[float | None] = mapped_column(Float)
    supplier_qty: Mapped[int | None] = mapped_column(Integer)
    length_mm: Mapped[int | None] = mapped_column(Integer)
    width_mm: Mapped[int | None] = mapped_column(Integer)
    height_mm: Mapped[int | None] = mapped_column(Integer)
    weight_g: Mapped[int | None] = mapped_column(Integer)
    barcodes_json: Mapped[list | None] = mapped_column(JSON, nullable=True)
    fbs_commission_percent: Mapped[float | None] = mapped_column(Float, nullable=True)
    fbo_commission_percent: Mapped[float | None] = mapped_column(Float, nullable=True)
    rfbs_commission_percent: Mapped[float | None] = mapped_column(Float, nullable=True)
    fbp_commission_percent: Mapped[float | None] = mapped_column(Float, nullable=True)
    stocks_json: Mapped[list | None] = mapped_column(JSON, nullable=True)
    has_stock: Mapped[bool] = mapped_column(Boolean, default=False)
    category_id: Mapped[int | None] = mapped_column(Integer, index=True)
    description_category_id: Mapped[int | None] = mapped_column(Integer, index=True)
    first_image_url: Mapped[str | None] = mapped_column(String(1500))
    price: Mapped[float | None] = mapped_column(Float)
    stock: Mapped[int | None] = mapped_column(Integer)
    warehouse_id: Mapped[int | None] = mapped_column(Integer, index=True)
    archived: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    visible: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    moderate_status: Mapped[str | None] = mapped_column(String(255), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
    shop: Mapped[OzonShop] = relationship(back_populates="products")
    raw_json: Mapped[dict | None] = mapped_column(JSON)

class OzonSyncLog(Base):
    __tablename__ = "ozon_sync_logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    shop_id: Mapped[int | None] = mapped_column(ForeignKey("ozon_shops.id"), nullable=True, index=True)
    sync_type: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(32), index=True)
    message: Mapped[str | None] = mapped_column(Text)
    items_total: Mapped[int] = mapped_column(Integer, default=0)
    items_success: Mapped[int] = mapped_column(Integer, default=0)
    items_failed: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
