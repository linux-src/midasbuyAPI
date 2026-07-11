"""
SQLAlchemy модели базы данных.
Таблицы: users, coupons, activation_logs.
"""
from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Базовый класс для всех моделей."""
    pass


class CouponStatus(str, PyEnum):
    """Статусы обработки купона."""
    PENDING = "pending"
    PROCESSING = "processing"
    SUCCESS = "success"
    FAILED = "failed"
    DUPLICATE = "duplicate"
    EXPIRED = "expired"
    INVALID = "invalid"


class User(Base):
    """Пользователь Telegram."""
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)  # Telegram user_id
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    first_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    is_banned: Mapped[bool] = mapped_column(Boolean, default=False)

    # Relationships
    coupons: Mapped[list["Coupon"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, username={self.username})>"


class Coupon(Base):
    """Купон, отправленный пользователем на активацию."""
    __tablename__ = "coupons"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(50), default=CouponStatus.PENDING.value
    )
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    activated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    error_msg: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)

    # Relationships
    user: Mapped["User"] = relationship(back_populates="coupons")
    logs: Mapped[list["ActivationLog"]] = relationship(
        back_populates="coupon", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Coupon(id={self.id}, code={self.code}, status={self.status})>"


class ActivationLog(Base):
    """Лог попытки активации купона."""
    __tablename__ = "activation_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    coupon_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("coupons.id"), nullable=False
    )
    attempt: Mapped[int] = mapped_column(Integer, default=1)
    result: Mapped[str | None] = mapped_column(Text, nullable=True)
    screenshot: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )

    # Relationships
    coupon: Mapped["Coupon"] = relationship(back_populates="logs")

    def __repr__(self) -> str:
        return f"<ActivationLog(id={self.id}, coupon_id={self.coupon_id}, attempt={self.attempt})>"
