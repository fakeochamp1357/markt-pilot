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

    deposit_cents: int = Field(0, ge=0)
    pieces_per_pack: int = Field(1, ge=1)
    pack_unit: str | None = Field(None, max_length=20)
    pack_barcode: str | None = Field(None, max_length=32)


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
    deposit_cents: int | None = Field(None, ge=0)
    pieces_per_pack: int | None = Field(None, ge=1)
    pack_unit: str | None = Field(None, max_length=20)
    pack_barcode: str | None = Field(None, max_length=32)


class ProductRead(ProductBase):
    """Response für GET — alle Felder inkl. DB-Metadaten."""

    id: int
    version: int
    created_at: datetime
    updated_at: datetime
    deposit_cents: int
    pieces_per_pack: int
    pack_unit: str | None
    pack_barcode: str | None
    # Preis sowohl als Decimal-String (fuer Display) als auch als int in Cent
    # (fuer mathefreie Berechnungen im Frontend, z.B. POS-Warenkorb).
    sell_price_cents: int
    cost_price_cents: int

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
            deposit_cents=obj.deposit_cents,
            pieces_per_pack=obj.pieces_per_pack,
            pack_unit=obj.pack_unit,
            pack_barcode=obj.pack_barcode,
            sell_price_cents=obj.sell_price_cents,
            cost_price_cents=obj.cost_price_cents,
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


# ---------------------------------------------------------------------------
# Receipt / POS
# ---------------------------------------------------------------------------


ReceiptKind = Literal["sale", "storno", "return"]
ReceiptLineKind = Literal["sale", "deposit", "return", "storno"]
PaymentMethod = Literal["cash", "card", "mixed"]


class ReceiptLineCreate(BaseModel):
    """Eine Position auf einem Kassenbon."""

    model_config = ConfigDict(from_attributes=True)

    kind: ReceiptLineKind = "sale"
    # product_id: optional, weil deposit-only / manuelle Pfandrueckgabe-
    # Positionen kein Produkt binden.
    product_id: int | None = None
    name_snapshot: str = Field(..., min_length=1, max_length=200)
    unit_snapshot: str = Field("Stück", max_length=20)
    quantity: QuantityDecimal
    unit_price_cents: int
    line_total_cents: int
    comment: str | None = Field(None, max_length=200)


class ReceiptCreate(BaseModel):
    """POST-Body für /api/receipts.

    Der Client baut den Bon im Cart zusammen (Produkt-Snapshots + ggf.
    Pfand-Positionen) und schickt ihn als Ganzes. Server validiert,
    generiert receipt_number, wendet Stock-Movements an und persistiert
    den Bon — alles in einer DB-Transaktion.
    """

    model_config = ConfigDict(from_attributes=True)

    kind: ReceiptKind = "sale"
    original_receipt_id: int | None = None
    cash_session: str = Field(..., min_length=1, max_length=40)
    payment_method: PaymentMethod = "cash"
    tendered_cents: int = Field(0, ge=0)
    change_cents: int = Field(0, ge=0)
    total_cents: int
    cashier_name: str | None = Field(None, max_length=80)
    notes: str | None = Field(None, max_length=500)
    print_requested: bool = True
    lines: list[ReceiptLineCreate] = Field(..., min_length=1)


class ReceiptLineRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    position: int
    kind: str
    product_id: int | None
    name_snapshot: str
    unit_snapshot: str
    quantity: Decimal
    unit_price_cents: int
    line_total_cents: int
    comment: str | None


class ReceiptRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    receipt_number: str
    kind: str
    original_receipt_id: int | None
    cash_session: str
    payment_method: str
    tendered_cents: int
    change_cents: int
    total_cents: int
    cashier_name: str | None
    notes: str | None
    print_requested: bool
    created_at: datetime
    lines: list[ReceiptLineRead]


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
    "ReceiptCreate",
    "ReceiptLineCreate",
    "ReceiptLineRead",
    "ReceiptRead",
    "cents_to_decimal",
    "decimal_to_cents",
]