"""Analytics-Service: Aggregationen über Stock-Bewegungen und Produkte.

Dieses Modul enthält die reine Berechnungslogik — keine FastAPI-Abhängigkeiten.
Alle Funktionen nehmen ein SQLAlchemy-Session und ein ``now``-Datum entgegen,
damit sie deterministisch testbar sind.

Designprinzipien:
- *Verkauf* = ``StockMovement`` mit ``reason='sale'`` und ``change < 0``.
  Der Abs-Wert (``|change|``) ist die verkaufte Menge.
- *Umsatz* = ``qty_sold * sell_price_cents`` (zum Zeitpunkt der Bewegung
  wird der aktuelle Verkaufspreis verwendet; im Supermarkt-Kontext mit
  seltenen Preisänderungen ist das eine sehr gute Näherung).
- *Marge* = ``Umsatz - Kosten`` mit ``Kosten = qty * cost_price_cents``.
- *Dead-Stock* = aktive Produkte ohne ``sale``-Movement innerhalb des
  Cutoff-Zeitraums.
- *MHD-Alerts* folgen den Schwellwerten in ``ExpiryAlert``-Funktion.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Iterable, Literal

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.models import Product, StockMovement

# ---------------------------------------------------------------------------
# Konstanten
# ---------------------------------------------------------------------------

# Mapping von benannten Perioden auf Tage. ``all`` = +∞ (kein Cutoff).
PERIOD_DAYS: dict[str, int | None] = {
    "week": 7,
    "month": 30,
    "quarter": 90,
    "year": 365,
    "all": None,
}

VALID_PERIODS: tuple[str, ...] = tuple(PERIOD_DAYS.keys())

# Standard-Schwellwert für „bald ablaufend" — konfigurierbar im Endpoint.
DEFAULT_EXPIRY_WARN_DAYS = 7

Severity = Literal["info", "warn", "danger"]
AlertType = Literal["expiry_soon", "expired", "reorder", "dead_stock"]


# ---------------------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------------------


def _cents(value: int) -> Decimal:
    """Cent-Integer → EUR-Decimal mit 2 Nachkommastellen."""
    return (Decimal(value) / Decimal(100)).quantize(Decimal("0.01"))


def _period_cutoff(period: str, now: datetime) -> datetime | None:
    """Cutoff-Zeitpunkt für eine benannte Periode. ``None`` = kein Cutoff."""
    if period not in PERIOD_DAYS:
        raise ValueError(
            f"Unbekannte Periode '{period}'. Erlaubt: {', '.join(VALID_PERIODS)}."
        )
    days = PERIOD_DAYS[period]
    if days is None:
        return None
    return now - timedelta(days=days)


def _as_aware_utc(dt: datetime | None) -> datetime | None:
    """Stellt sicher, dass ein datetime-Wert tz-aware UTC ist.

    SQLite speichert ``DateTime(timezone=True)`` ohne TZ-Info (SQLite kennt
    keine echten Zeitzonen). Beim Re-Hydrieren kommen naive ``datetime``-
    Objekte zurück. Für Differenzen mit einem tz-aware ``now`` normalisieren
    wir hier auf UTC.
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


# ---------------------------------------------------------------------------
# Ergebnisse — Datenklassen, die der Service liefert (Router mappt auf Schemas)
# ---------------------------------------------------------------------------


@dataclass
class TopSeller:
    product_id: int
    name: str
    qty_sold: Decimal
    revenue_cents: int
    margin_cents: int
    margin_pct: Decimal


@dataclass
class MarginRow:
    product_id: int
    name: str
    qty_sold: Decimal
    revenue_cents: int
    cost_cents: int
    margin_cents: int
    margin_pct: Decimal


@dataclass
class DeadStockRow:
    product_id: int
    name: str
    sku: str | None
    last_sale_at: datetime | None
    days_since_last_sale: int | None
    stock_quantity: Decimal
    stock_value_cents: int


@dataclass
class ExpiryAlertRow:
    product_id: int
    name: str
    expiry_date: date
    days_until_expiry: int
    stock_quantity: Decimal
    severity: Severity


@dataclass
class ReorderRow:
    product_id: int
    name: str
    sku: str | None
    stock_quantity: Decimal
    min_stock_level: Decimal
    deficit: Decimal
    suggested_order_qty: Decimal


@dataclass
class DashboardSummary:
    total_active_products: int
    total_inventory_value_cents: int
    total_sales_period_cents: int
    total_margin_period_cents: int
    units_sold_period: Decimal
    expiry_soon_count: int
    expired_count: int
    reorder_count: int
    dead_stock_count: int
    period: str


@dataclass
class Notification:
    type: AlertType
    severity: Severity
    product_id: int
    product_name: str
    message: str
    created_at: datetime


# ---------------------------------------------------------------------------
# Kernfunktionen
# ---------------------------------------------------------------------------


def top_sellers(
    db: Session,
    *,
    period: str = "month",
    limit: int = 20,
    sort_by: Literal["qty", "revenue", "margin"] = "qty",
    now: datetime | None = None,
) -> list[TopSeller]:
    """Meistverkaufte Produkte im Zeitraum.

    Aggregiert ``StockMovement(reason='sale', change<0)`` je Produkt.
    """
    if now is None:
        now = datetime.now(timezone.utc)
    cutoff = _period_cutoff(period, now)

    # Aggregation: SUM(ABS(change)) je product_id.
    abs_change = func.coalesce(func.sum(func.abs(StockMovement.change)), 0).label(
        "qty_sold"
    )

    stmt = (
        select(
            StockMovement.product_id.label("pid"),
            abs_change,
        )
        .where(StockMovement.reason == "sale", StockMovement.change < 0)
        .group_by(StockMovement.product_id)
    )
    if cutoff is not None:
        stmt = stmt.where(StockMovement.created_at >= cutoff)
    rows = db.execute(stmt).all()

    if not rows:
        return []

    # Produkte in einem Schwung laden (vermeidet N+1).
    pids = [r.pid for r in rows]
    products = {
        p.id: p
        for p in db.execute(
            select(Product).where(Product.id.in_(pids), Product.is_active.is_(True))
        ).scalars()
    }

    out: list[TopSeller] = []
    for r in rows:
        prod = products.get(r.pid)
        if prod is None:
            continue  # inaktiv oder gelöscht → überspringen
        qty = Decimal(r.qty_sold)
        revenue_cents = int(qty * Decimal(prod.sell_price_cents))
        cost_cents = int(qty * Decimal(prod.cost_price_cents))
        margin_cents = revenue_cents - cost_cents
        margin_pct = (
            (Decimal(margin_cents) / Decimal(revenue_cents) * Decimal(100))
            if revenue_cents > 0
            else Decimal("0")
        )
        out.append(
            TopSeller(
                product_id=prod.id,
                name=prod.name,
                qty_sold=qty,
                revenue_cents=revenue_cents,
                margin_cents=margin_cents,
                margin_pct=margin_pct.quantize(Decimal("0.01")),
            )
        )

    if sort_by == "qty":
        out.sort(key=lambda x: x.qty_sold, reverse=True)
    elif sort_by == "revenue":
        out.sort(key=lambda x: x.revenue_cents, reverse=True)
    elif sort_by == "margin":
        out.sort(key=lambda x: x.margin_cents, reverse=True)
    else:
        raise ValueError(f"Unbekannter sort_by='{sort_by}'.")

    return out[:limit]


def margins(
    db: Session,
    *,
    period: str = "month",
    limit: int = 50,
    only_with_sales: bool = True,
    now: datetime | None = None,
) -> list[MarginRow]:
    """Marge pro Produkt im Zeitraum — nach absoluter Marge sortiert."""
    if now is None:
        now = datetime.now(timezone.utc)
    cutoff = _period_cutoff(period, now)

    abs_change = func.coalesce(func.sum(func.abs(StockMovement.change)), 0).label(
        "qty_sold"
    )

    stmt = (
        select(
            StockMovement.product_id.label("pid"),
            abs_change,
        )
        .where(StockMovement.reason == "sale", StockMovement.change < 0)
        .group_by(StockMovement.product_id)
    )
    if cutoff is not None:
        stmt = stmt.where(StockMovement.created_at >= cutoff)
    rows = db.execute(stmt).all()

    sales_by_pid = {r.pid: Decimal(r.qty_sold) for r in rows}

    # Alle aktiven Produkte holen (auch ohne Sales — ``only_with_sales=False``).
    if only_with_sales:
        pids = list(sales_by_pid.keys())
        if not pids:
            return []
        products = list(
            db.execute(
                select(Product).where(Product.id.in_(pids), Product.is_active.is_(True))
            ).scalars()
        )
    else:
        products = list(
            db.execute(
                select(Product).where(Product.is_active.is_(True))
            ).scalars()
        )

    out: list[MarginRow] = []
    for prod in products:
        qty = sales_by_pid.get(prod.id, Decimal("0"))
        revenue_cents = int(qty * Decimal(prod.sell_price_cents))
        cost_cents = int(qty * Decimal(prod.cost_price_cents))
        margin_cents = revenue_cents - cost_cents
        margin_pct = (
            (Decimal(margin_cents) / Decimal(revenue_cents) * Decimal(100))
            if revenue_cents > 0
            else Decimal("0")
        )
        out.append(
            MarginRow(
                product_id=prod.id,
                name=prod.name,
                qty_sold=qty,
                revenue_cents=revenue_cents,
                cost_cents=cost_cents,
                margin_cents=margin_cents,
                margin_pct=margin_pct.quantize(Decimal("0.01")),
            )
        )

    # Ohne Sales ans Ende; der Rest nach Marge desc.
    out.sort(key=lambda r: (r.revenue_cents == 0, -r.margin_cents))
    return out[:limit]


def dead_stock(
    db: Session,
    *,
    period: str = "month",
    limit: int = 100,
    include_zero_stock: bool = True,
    now: datetime | None = None,
) -> list[DeadStockRow]:
    """Produkte ohne Verkäufe im Zeitraum.

    Schwellwert:
    - 'week'/'month'/'quarter'/'year'  → nur Sales SEIT dem Cutoff zählen
    - 'all'                            → jeder aktive Sale rettet das Produkt

    ``include_zero_stock=False`` filtert Produkte mit Bestand = 0 heraus,
    weil die ohnehin nichts mehr zum Verkauf beitragen.

    Hinweis: ``last_sale_at`` ist das letzte Sale-Datum ÜBERHAUPT (nicht im
    Zeitraum), damit man sieht, wann das Produkt zuletzt überhaupt verkauft
    wurde — oder ``None`` für „nie verkauft".
    """
    if now is None:
        now = datetime.now(timezone.utc)
    cutoff = _period_cutoff(period, now)

    # 1) Subquery: gibt es IRGENDEINEN Sale im Zeitraum?
    in_period_sales = (
        select(StockMovement.product_id)
        .where(StockMovement.reason == "sale", StockMovement.change < 0)
    )
    if cutoff is not None:
        in_period_sales = in_period_sales.where(StockMovement.created_at >= cutoff)
    in_period_sales = in_period_sales.group_by(StockMovement.product_id).subquery()

    # 2) Aktive Produkte, die KEINEN Sale im Zeitraum hatten.
    stmt = (
        select(Product)
        .where(
            Product.is_active.is_(True),
            Product.id.notin_(select(in_period_sales.c.product_id)),
        )
    )
    if not include_zero_stock:
        stmt = stmt.where(Product.stock_quantity > 0)
    stmt = stmt.order_by(Product.id)
    products = list(db.execute(stmt).scalars().all())

    if not products:
        return []

    # 3) Für jedes Dead-Stock-Produkt das letzte Sale-Datum ÜBERHAUPT.
    pids = [p.id for p in products]
    last_any = (
        select(
            StockMovement.product_id.label("pid"),
            func.max(StockMovement.created_at).label("last_sale"),
        )
        .where(
            StockMovement.product_id.in_(pids),
            StockMovement.reason == "sale",
            StockMovement.change < 0,
        )
        .group_by(StockMovement.product_id)
    )
    last_any_rows = db.execute(last_any).all()
    last_any_map: dict[int, datetime] = {r.pid: r.last_sale for r in last_any_rows}

    out: list[DeadStockRow] = []
    for prod in products:
        last_sale = last_any_map.get(prod.id)
        last_sale_aware = _as_aware_utc(last_sale)
        days_since: int | None = (
            (now - last_sale_aware).days if last_sale_aware is not None else None
        )
        out.append(
            DeadStockRow(
                product_id=prod.id,
                name=prod.name,
                sku=prod.sku,
                last_sale_at=last_sale,
                days_since_last_sale=days_since,
                stock_quantity=Decimal(prod.stock_quantity),
                stock_value_cents=int(
                    Decimal(prod.stock_quantity) * Decimal(prod.sell_price_cents)
                ),
            )
        )
        if len(out) >= limit:
            break

    return out


def expiry_alerts(
    db: Session,
    *,
    warn_days: int = DEFAULT_EXPIRY_WARN_DAYS,
    include_expired: bool = True,
    limit: int = 200,
    today: date | None = None,
) -> list[ExpiryAlertRow]:
    """MHD-Warnungen — bald ablaufend und/oder bereits abgelaufen.

    ``warn_days`` ist der Schwellwert in Tagen; alles innerhalb dieses
    Fensters bekommt ``severity='warn'``, abgelaufene ``severity='danger'``.
    """
    if today is None:
        today = date.today()
    cutoff = today + timedelta(days=warn_days)

    stmt = (
        select(Product)
        .where(
            Product.is_active.is_(True),
            Product.expiry_date.is_not(None),
            Product.expiry_date <= cutoff,
        )
        .order_by(Product.expiry_date.asc())
    )

    rows = db.execute(stmt).scalars().all()

    out: list[ExpiryAlertRow] = []
    for prod in rows:
        assert prod.expiry_date is not None  # mypy: stmt filter
        delta = (prod.expiry_date - today).days
        if delta < 0:
            if not include_expired:
                continue
            severity: Severity = "danger"
        elif delta <= warn_days:
            severity = "warn"
        else:
            # Sollte durch Cutoff nicht passieren, aber defensiv.
            continue
        out.append(
            ExpiryAlertRow(
                product_id=prod.id,
                name=prod.name,
                expiry_date=prod.expiry_date,
                days_until_expiry=delta,
                stock_quantity=Decimal(prod.stock_quantity),
                severity=severity,
            )
        )
        if len(out) >= limit:
            break
    return out


def reorder_alerts(
    db: Session,
    *,
    include_zero_min: bool = False,
    suggest_order_to: Decimal | None = None,
    limit: int = 200,
) -> list[ReorderRow]:
    """Nachbestell-Vorschläge — Produkte unter Mindestbestand.

    ``suggest_order_to`` = Ziel-Bestand nach Lieferung (Default: 2× Mindestbestand).
    """
    stmt = (
        select(Product)
        .where(
            Product.is_active.is_(True),
            Product.stock_quantity < Product.min_stock_level,
        )
        .order_by((Product.min_stock_level - Product.stock_quantity).desc())
    )
    if not include_zero_min:
        stmt = stmt.where(Product.min_stock_level > 0)

    rows = db.execute(stmt).scalars().all()

    out: list[ReorderRow] = []
    for prod in rows:
        current = Decimal(prod.stock_quantity)
        minimum = Decimal(prod.min_stock_level)
        deficit = minimum - current
        if suggest_order_to is not None:
            order_qty = max(Decimal("0"), suggest_order_to - current)
        else:
            # 2× Mindestbestand auffüllen — gängige Praxis im LEH.
            order_qty = max(deficit, minimum)
        out.append(
            ReorderRow(
                product_id=prod.id,
                name=prod.name,
                sku=prod.sku,
                stock_quantity=current,
                min_stock_level=minimum,
                deficit=deficit,
                suggested_order_qty=order_qty.quantize(Decimal("0.001")),
            )
        )
        if len(out) >= limit:
            break
    return out


def dashboard_summary(
    db: Session,
    *,
    period: str = "month",
    warn_days: int = DEFAULT_EXPIRY_WARN_DAYS,
    now: datetime | None = None,
) -> DashboardSummary:
    """Aggregierte KPIs für die Dashboard-Ansicht."""
    if now is None:
        now = datetime.now(timezone.utc)

    # Aktive Produkte + Lagerwert.
    active_products = list(
        db.execute(
            select(Product).where(Product.is_active.is_(True))
        ).scalars()
    )
    total_active = len(active_products)
    total_value_cents = sum(
        int(Decimal(p.stock_quantity) * Decimal(p.sell_price_cents))
        for p in active_products
    )

    # Sales-KPIs.
    sellers = top_sellers(db, period=period, limit=10_000, now=now)
    total_revenue = sum(s.revenue_cents for s in sellers)
    total_margin = sum(s.margin_cents for s in sellers)
    units_sold = sum((s.qty_sold for s in sellers), Decimal("0"))

    # Alerts-Counts.
    soon, expired = _split_expiry(
        expiry_alerts(db, warn_days=warn_days, include_expired=True, limit=10_000)
    )
    reorders = reorder_alerts(db, limit=10_000)
    dead = dead_stock(db, period=period, limit=10_000, now=now)

    return DashboardSummary(
        total_active_products=total_active,
        total_inventory_value_cents=total_value_cents,
        total_sales_period_cents=total_revenue,
        total_margin_period_cents=total_margin,
        units_sold_period=units_sold,
        expiry_soon_count=len(soon),
        expired_count=len(expired),
        reorder_count=len(reorders),
        dead_stock_count=len(dead),
        period=period,
    )


def aggregate_notifications(
    db: Session,
    *,
    period: str = "month",
    warn_days: int = DEFAULT_EXPIRY_WARN_DAYS,
    now: datetime | None = None,
) -> list[Notification]:
    """Sammelt alle Alerts in einer einzigen Liste (UI-Badge, Banner).

    Sortierung: Gefahr zuerst (danger), dann warn, dann info; innerhalb
    der Severity nach Zeit (frischere zuerst — created_at=now als Proxy).
    """
    if now is None:
        now = datetime.now(timezone.utc)

    notes: list[Notification] = []

    for ex in expiry_alerts(db, warn_days=warn_days, limit=500):
        if ex.severity == "danger":
            msg = f"MHD abgelaufen seit {-ex.days_until_expiry} Tag(en)"
        elif ex.days_until_expiry == 0:
            msg = "Läuft heute ab"
        else:
            msg = f"Läuft in {ex.days_until_expiry} Tag(en) ab"
        notes.append(
            Notification(
                type="expiry_soon" if ex.severity == "warn" else "expired",
                severity=ex.severity,
                product_id=ex.product_id,
                product_name=ex.name,
                message=msg,
                created_at=now,
            )
        )

    for r in reorder_alerts(db, limit=500):
        deficit_int = int(r.deficit) if r.deficit == int(r.deficit) else float(r.deficit)
        notes.append(
            Notification(
                type="reorder",
                severity="warn",
                product_id=r.product_id,
                product_name=r.name,
                message=(
                    f"Nachbestellen: aktuell {r.stock_quantity.normalize()} "
                    f"{_unit_hint(r.product_id, db)}, "
                    f"Mindest {r.min_stock_level.normalize()}"
                ),
                created_at=now,
            )
        )

    for d in dead_stock(db, period=period, limit=500, now=now):
        notes.append(
            Notification(
                type="dead_stock",
                severity="info",
                product_id=d.product_id,
                product_name=d.name,
                message=(
                    f"Keine Verkäufe im Zeitraum — "
                    f"{d.stock_quantity.normalize()} auf Lager"
                ),
                created_at=now,
            )
        )

    severity_order = {"danger": 0, "warn": 1, "info": 2}
    notes.sort(key=lambda n: (severity_order.get(n.severity, 9), -0))
    return notes


# ---------------------------------------------------------------------------
# Private Helpers
# ---------------------------------------------------------------------------


def _split_expiry(
    rows: Iterable[ExpiryAlertRow],
) -> tuple[list[ExpiryAlertRow], list[ExpiryAlertRow]]:
    soon = [r for r in rows if r.severity == "warn"]
    expired = [r for r in rows if r.severity == "danger"]
    return soon, expired


def _unit_hint(product_id: int, db: Session) -> str:
    """Liest die Unit einmal nach; für hübsche Notification-Texte."""
    prod = db.get(Product, product_id)
    return prod.unit if prod else "Stück"


__all__ = [
    "PERIOD_DAYS",
    "VALID_PERIODS",
    "DEFAULT_EXPIRY_WARN_DAYS",
    "TopSeller",
    "MarginRow",
    "DeadStockRow",
    "ExpiryAlertRow",
    "ReorderRow",
    "DashboardSummary",
    "Notification",
    "top_sellers",
    "margins",
    "dead_stock",
    "expiry_alerts",
    "reorder_alerts",
    "dashboard_summary",
    "aggregate_notifications",
]