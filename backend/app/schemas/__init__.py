"""Pydantic v2 Schemas für die API.

Wichtige Konventionen:
- Preise werden in der DB als INTEGER-Cent gespeichert.
- An der API-Grenze erscheinen sie als Decimal (EUR).
- Felder in PascalCase für API, snake_case intern.
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

PriceDecimal = Annotated[
    Decimal,
    Field(
        max_digits=12,
        decimal_places=2,
        description="Betrag in EUR (z.B. 1.99)",
    ),
]

QuantityDecimal = Annotated[
    Decimal,
    Field(
        max_digits=14,
        decimal_places=3,
        description="Mengenangabe (Stück, kg, g, l, ml …)",
    ),
]


def cents_to_decimal(cents: int) -> Decimal:
    return (Decimal(cents) / Decimal(100)).quantize(Decimal("0.01"))


def decimal_to_cents(value: Decimal | float | int | str | None) -> int:
    if value is None:
        return 0
    return int((Decimal(str(value)) * 100).quantize(Decimal("1")))


# ---------------------------------------------------------------------------
# Category
# ---------------------------------------------------------------------------


class CategoryBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str = Field(..., min_length=1, max_length=120)
    color: str = Field("#3B82F6", pattern=r"^#[0-9A-Fa-f]{6}$")
    sort_order: int = Field(0, ge=0)
    parent_id: int | None = None


class CategoryCreate(CategoryBase):
    pass


class CategoryUpdate(BaseModel):
    """Alle Felder optional für PATCH-artige Updates."""

    model_config = ConfigDict(from_attributes=True)

    name: str | None = Field(None, min_length=1, max_length=120)
    color: str | None = Field(None, pattern=r"^#[0-9A-Fa-f]{6}$")
    sort_order: int | None = Field(None, ge=0)
    parent_id: int | None = None


class CategoryRead(CategoryBase):
    id: int
    created_at: datetime


# ---------------------------------------------------------------------------
# Product
# ---------------------------------------------------------------------------


class ProductBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    sku: str | None = Field(None, max_length=64)
    barcode: str | None = Field(None, max_length=32)
    name: str = Field(..., min_length=1, max_length=200)
    category_id: int | None = None
    unit: str = Field("Stück", max_length=20)
    size_weight: str | None = Field(None, max_length=40)
    cost_price: PriceDecimal = Field(default=Decimal("0"))
    sell_price: PriceDecimal = Field(default=Decimal("0"))
    currency: str = Field("EUR", min_length=3, max_length=3)
    stock_quantity: QuantityDecimal = Field(default=Decimal("0"))
    min_stock_level: QuantityDecimal = Field(default=Decimal("0"))
    expiry_date: date | None = None
    supplier: str | None = Field(None, max_length=200)
    notes: str | None = Field(None, max_length=1000)
    image_url: str | None = Field(None, max_length=500)
    color_tag: str = Field("#3B82F6", pattern=r"^#[0-9A-Fa-f]{6}$")
    is_active: bool = True


class ProductCreate(ProductBase):
    """POST-Body für /api/products."""


class ProductUpdate(BaseModel):
    """Alle Felder optional — wird für PUT verwendet."""

    model_config = ConfigDict(from_attributes=True)

    sku: str | None = Field(None, max_length=64)
    barcode: str | None = Field(None, max_length=32)
    name: str | None = Field(None, min_length=1, max_length=200)
    category_id: int | None = None
    unit: str | None = Field(None, max_length=20)
    size_weight: str | None = Field(None, max_length=40)
    cost_price: PriceDecimal | None = None
    sell_price: PriceDecimal | None = None
    currency: str | None = Field(None, min_length=3, max_length=3)
    stock_quantity: QuantityDecimal | None = None
    min_stock_level: QuantityDecimal | None = None
    expiry_date: date | None = None
    supplier: str | None = Field(None, max_length=200)
    notes: str | None = Field(None, max_length=1000)
    image_url: str | None = Field(None, max_length=500)
    color_tag: str | None = Field(None, pattern=r"^#[0-9A-Fa-f]{6}$")
    is_active: bool | None = None


class ProductRead(ProductBase):
    """Response für GET — alle Felder inkl. DB-Metadaten."""

    id: int
    version: int
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_orm_product(cls, obj) -> "ProductRead":
        """Mappt ORM-Produkt → API-Schema (Cent → EUR)."""
        return cls(
            id=obj.id,
            sku=obj.sku,
            barcode=obj.barcode,
            name=obj.name,
            category_id=obj.category_id,
            unit=obj.unit,
            size_weight=obj.size_weight,
            cost_price=cents_to_decimal(obj.cost_price_cents),
            sell_price=cents_to_decimal(obj.sell_price_cents),
            currency=obj.currency,
            stock_quantity=Decimal(obj.stock_quantity),
            min_stock_level=Decimal(obj.min_stock_level),
            expiry_date=obj.expiry_date,
            supplier=obj.supplier,
            notes=obj.notes,
            image_url=obj.image_url,
            color_tag=obj.color_tag,
            is_active=obj.is_active,
            version=obj.version,
            created_at=obj.created_at,
            updated_at=obj.updated_at,
        )


class ProductListResponse(BaseModel):
    items: list[ProductRead]
    total: int
    limit: int
    offset: int


# ---------------------------------------------------------------------------
# Bulk-Import
# ---------------------------------------------------------------------------


class ProductBulkItem(ProductBase):
    """Einzelnes Item für Bulk-Import — barcode ODER sku dient als Dedup-Key."""


class ProductBulkRequest(BaseModel):
    items: list[ProductBulkItem] = Field(..., min_length=1)


class ProductBulkResult(BaseModel):
    created: int
    updated: int
    skipped: int
    errors: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Stock
# ---------------------------------------------------------------------------

StockReason = Literal["purchase", "sale", "adjustment", "waste", "return"]


class StockMovementCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    product_id: int
    change: QuantityDecimal
    reason: StockReason = "adjustment"
    reference: str | None = Field(None, max_length=120)
    created_by: str | None = Field(None, max_length=120)


class StockMovementRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    product_id: int
    change: Decimal
    reason: str
    reference: str | None
    created_by: str | None
    created_at: datetime


class StockMovementList(BaseModel):
    items: list[StockMovementRead]
    total: int


class LowStockProduct(BaseModel):
    """Ein Low-Stock-Hit — kompakte Form."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    sku: str | None
    barcode: str | None
    category_id: int | None
    stock_quantity: Decimal
    min_stock_level: Decimal
    unit: str
    color_tag: str
    deficit: Decimal  # min - current (>0)

    @classmethod
    def from_orm(cls, obj) -> "LowStockProduct":
        deficit = Decimal(obj.min_stock_level) - Decimal(obj.stock_quantity)
        return cls(
            id=obj.id,
            name=obj.name,
            sku=obj.sku,
            barcode=obj.barcode,
            category_id=obj.category_id,
            stock_quantity=Decimal(obj.stock_quantity),
            min_stock_level=Decimal(obj.min_stock_level),
            unit=obj.unit,
            color_tag=obj.color_tag,
            deficit=deficit,
        )


class ExpiringProduct(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    sku: str | None
    barcode: str | None
    expiry_date: date
    days_until_expiry: int
    stock_quantity: Decimal
    color_tag: str

    @classmethod
    def from_orm(cls, obj, today: date) -> "ExpiringProduct":
        delta = (obj.expiry_date - today).days
        return cls(
            id=obj.id,
            name=obj.name,
            sku=obj.sku,
            barcode=obj.barcode,
            expiry_date=obj.expiry_date,
            days_until_expiry=delta,
            stock_quantity=Decimal(obj.stock_quantity),
            color_tag=obj.color_tag,
        )


# CSV-Import Re-Export
__all__ = [
    "CategoryBase",
    "CategoryCreate",
    "CategoryUpdate",
    "CategoryRead",
    "ProductBase",
    "ProductCreate",
    "ProductUpdate",
    "ProductRead",
    "ProductListResponse",
    "ProductBulkItem",
    "ProductBulkRequest",
    "ProductBulkResult",
    "StockMovementCreate",
    "StockMovementRead",
    "StockMovementList",
    "LowStockProduct",
    "ExpiringProduct",
    "cents_to_decimal",
    "decimal_to_cents",
]