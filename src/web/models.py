from datetime import datetime
from sqlalchemy import Boolean, DateTime, Integer, String, func, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.app.db import Base


class WebUser(Base):
    __tablename__ = "web_users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    username: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))

    role: Mapped[str] = mapped_column(String(50), default="courier", index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class CourierActionLog(Base):
    __tablename__ = "courier_action_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    user_id: Mapped[int | None] = mapped_column(ForeignKey("web_users.id"), nullable=True)
    username: Mapped[str | None] = mapped_column(String(255))

    posting_id: Mapped[int | None] = mapped_column(ForeignKey("ozon_postings.id"), nullable=True)
    posting_number: Mapped[str | None] = mapped_column(String(255), index=True)

    action: Mapped[str] = mapped_column(String(100), index=True)
    old_status: Mapped[str | None] = mapped_column(String(100))
    new_status: Mapped[str | None] = mapped_column(String(100))

    comment: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
