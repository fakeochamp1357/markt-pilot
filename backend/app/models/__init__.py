"""SQLAlchemy ORM models for MarktPilot.

Preise werden intern als Integer-Cent gespeichert
(cost_price_cents, sell_price_cents). An der API-Grenze werden sie via
Pydantic in Decimal umgewandelt.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Category(Base):
    """Produkt-Kategorie (optional hierarchisch via parent_id)."""

    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False, index=True)
    color: Mapped[str] = mapped_column(String(9), nullable=False, default="#3B82F6")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("categories.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    children: Mapped[list["Category"]] = relationship(
        "Category",
        back_populates="parent",
        remote_side="Category.id",
        cascade="all",
    )
    parent: Mapped["Category | None"] = relationship(
        "Category",
        back_populates="children",
        remote_side="Category.parent_id",
    )
    products: Mapped[list["Product"]] = relationship(
        "Product", back_populates="category"
    )


class Product(Base):
    """Das Herzstück der Preisliste — ein Produkt im Markt."""

    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sku: Mapped[str | None] = mapped_column(
        String(64), nullable=True, unique=True, index=True
    )
    barcode: Mapped[str | None] = mapped_column(
        String(32), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)

    category_id: Mapped[int | None] = mapped_column(
        ForeignKey("categories.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    unit: Mapped[str] = mapped_column(String(20), nullable=False, default="Stück")
    size_weight: Mapped[str | None] = mapped_column(String(40), nullable=True)

    # Preise in INTEGER-Cent (1.00 EUR = 100). Niemals Float.
    cost_price_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sell_price_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="EUR")

    # Bestand und Schwellwert — Decimal für kg/g/ml möglich.
    stock_quantity: Mapped[Decimal] = mapped_column(
        Numeric(14, 3), nullable=False, default=Decimal("0")
    )
    min_stock_level: Mapped[Decimal] = mapped_column(
        Numeric(14, 3), nullable=False, default=Decimal("0")
    )

    expiry_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    supplier: Mapped[str | None] = mapped_column(String(200), nullable=True)
    notes: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    color_tag: Mapped[str] = mapped_column(
        String(9), nullable=False, default="#3B82F6"
    )

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        onupdate=_utcnow,
    )

    # Optimistic locking — wird bei Stock-Movement-CAS verwendet.
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    category: Mapped["Category | None"] = relationship("Category", back_populates="products")
    stock_movements: Mapped[list["StockMovement"]] = relationship(
        "StockMovement",
        back_populates="product",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        # Composite-Index für häufige Filter (Aktiv + Kategorie).
        Index("ix_products_active_category", "is_active", "category_id"),
    )


# Reason-Enum für Stock-Movement als String-Constante (kein SQLAlchemy-Enum,
# damit Alembic-Migrationen portabel bleiben).
STOCK_REASONS = ("purchase", "sale", "adjustment", "waste", "return")


class StockMovement(Base):
    """Wareneingang, Verkauf, Korrektur, Verlust, Retoure."""

    __tablename__ = "stock_movements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # +/- Delta (z.B. +50 bei Wareneingang, -1 bei Verkauf).
    change: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    reason: Mapped[str] = mapped_column(String(20), nullable=False, default="adjustment")
    reference: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    product: Mapped["Product"] = relationship("Product", back_populates="stock_movements")