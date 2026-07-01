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

    # Pfand pro Stueck (in Cent), 0 fuer artikel ohne Pfand
    # (z.B. 25 fuer Getraenkedosen mit 0,25 EUR Einwegpfand).
    deposit_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Packungs-Information: pieces_per_pack > 1 bedeutet "wird in
    # Packungen eingekauft". Z.B. Vimto 24er-Tray = 24 Dosen.
    # Bestand wird in Stueck gefuehrt; Wareneingang kann in Packungen
    # gebucht werden (qty * pieces_per_pack).
    pieces_per_pack: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    # Optionale Einheit der Packung, z.B. "Tray" oder "Karton".
    pack_unit: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # Optional: eigener Barcode der Packung (z.B. Tray-Barcode != Dosen-Barcode).
    pack_barcode: Mapped[str | None] = mapped_column(
        String(32), nullable=True, index=True
    )

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


class ProcessedOp(Base):
    """Idempotenz-Cache: pro (client_op_id, endpoint) wird die erste Server-Antwort
    gespeichert, damit Retries dieselbe Antwort bekommen — keine Duplikate.

    Wird vom Frontend-Outbox genutzt, das bei Verbindungsabbruch die Anfrage
    erneut sendet. Ohne diesen Cache würde z.B. ein zweiter
    ``POST /api/products``-Call mit demselben Payload zwei Produkte anlegen,
    oder ein zweiter ``POST /api/stock/movements``-Call den Bestand doppelt
    verändern.
    """

    __tablename__ = "processed_ops"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # UUID-vom-Client, max 64 chars (z.B. "01J..." für ULID oder klassisches v4)
    client_op_id: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True, index=True
    )
    # Endpoint-Pfad, damit klar ist, wofür das Idempotenz-Token gilt
    endpoint: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    # HTTP-Statuscode der ursprünglichen Antwort
    status_code: Mapped[int] = mapped_column(Integer, nullable=False)
    # JSON-Body der ursprünglichen Antwort, zum erneuten Zurückgeben
    response_json: Mapped[str] = mapped_column(String(2000), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )


# Receipt-Kind: Verkaufs-, Storno- oder Retourbon.
# Storno = macht einen vorherigen Verkauf rückgängig (Tagesabschluss).
# Retoure = ein Kunde bringt Ware zurück und bekommt Geld.
RECEIPT_KINDS = ("sale", "storno", "return")
# Wie bezahlt wurde. "mixed" = mehrere Methoden (Bargeld + Karte).
PAYMENT_METHODS = ("cash", "card", "mixed")


class Receipt(Base):
    """Kassenbon — Header.

    Ein Bon gehört zu genau einem ``cash_session_id`` (Tagesabschluss/Schicht),
    aber für Phase A ist das nur ein loser String (Datum oder Schicht-Name).
    """

    __tablename__ = "receipts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # Menschenlesbare Bon-Nummer, fortlaufend pro Tag. Wird vom Server vergeben.
    receipt_number: Mapped[str] = mapped_column(
        String(40), nullable=False, unique=True, index=True
    )
    # 'sale', 'storno', 'return'
    kind: Mapped[str] = mapped_column(String(16), nullable=False, default="sale")
    # Optionale Verknüpfung: Storno/Retoure zeigt auf den ursprünglichen Bon.
    original_receipt_id: Mapped[int | None] = mapped_column(
        ForeignKey("receipts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    # Schicht-Kennung (z.B. Datum). Später ein eigener CashSession-Table.
    cash_session: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    # Bezahlung
    payment_method: Mapped[str] = mapped_column(
        String(16), nullable=False, default="cash"
    )
    tendered_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    change_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Total inkl. Pfand, in Cent. Negativ bei Storno/Retoure.
    total_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Mitarbeiter (frei Text, kein Login in Phase A — Mitarbeiterloyalität)
    cashier_name: Mapped[str | None] = mapped_column(String(80), nullable=True)
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, index=True
    )

    lines: Mapped[list["ReceiptLine"]] = relationship(
        "ReceiptLine",
        back_populates="receipt",
        cascade="all, delete-orphan",
        order_by="ReceiptLine.position",
    )


class ReceiptLine(Base):
    """Einzelposition auf einem Kassenbon.

    Line-Kinds:
      - 'sale'    : regulärer Verkauf (qty * unit_price > 0)
      - 'deposit' : Pfand-Anteil (qty = Bon-Stueck-Zahl, unit_price = Pfand-Cent)
      - 'return'  : Rücknahme (positiv im Retoure-Bon, negativ in Sale-Bon)
      - 'storno'  : Storno-Position (immer negativ)
    """

    __tablename__ = "receipt_lines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    receipt_id: Mapped[int] = mapped_column(
        ForeignKey("receipts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Position in der Reihenfolge auf dem Bon
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Welche Art von Zeile (sale/deposit/return/storno)
    kind: Mapped[str] = mapped_column(String(16), nullable=False, default="sale")
    # Optional: das verkaufte Produkt. Pfand-only-Positionen haben ggf. kein
    # product_id (z.B. Pfand-Rückgabe ohne zugehöriges Produkt).
    product_id: Mapped[int | None] = mapped_column(
        ForeignKey("products.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    # Snapshot von Name/Größe zum Zeitpunkt des Verkaufs — Bon bleibt lesbar,
    # auch wenn das Produkt später gelöscht/umbenannt wird.
    name_snapshot: Mapped[str] = mapped_column(String(200), nullable=False)
    unit_snapshot: Mapped[str] = mapped_column(String(20), nullable=False, default="Stück")
    # Menge (Decimal für kg/g/ml bei Wiegeware)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    # Einzelpreis in Cent (kann negativ sein bei Storno/Retoure)
    unit_price_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    # Zeilensumme (quantity * unit_price, gerundet in Cent)
    line_total_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    # Optionaler Kommentar (z.B. "Wurst 100g" bei Wiegeware)
    comment: Mapped[str | None] = mapped_column(String(200), nullable=True)

    receipt: Mapped["Receipt"] = relationship("Receipt", back_populates="lines")