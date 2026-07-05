"""Analytics-Router: Auswertungen über Stock-Bewegungen und Produkte.

Endpoints (alle unter ``/api/analytics``):
- GET /top-sellers           — meistverkaufte Produkte
- GET /margins               — Marge pro Produkt
- GET /dead-stock            — Ladenhüter (keine Sales im Zeitraum)
- GET /expiry-alerts         — MHD-Warnungen (bald abgelaufen / abgelaufen)
- GET /reorder-alerts        — Nachbestell-Vorschläge
- GET /dashboard/summary     — aggregierte KPIs
- GET /notifications         — gesammelte Alerts (für UI-Badge)
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas import (
    DashboardSummary,
    DeadStockRow,
    ExpiryAlert,
    MarginRow,
    NotificationItem,
    ReorderAlert,
    TopSeller,
)
from app.services import analytics

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


# ---------------------------------------------------------------------------
# Lokale Query-Validierung — gleiche Periode wie im Service.
# ---------------------------------------------------------------------------
_PeriodLiteral = Query(
    "month",
    description="Zeitraum: week|month|quarter|year|all",
    pattern="^(week|month|quarter|year|all)$",
)


def _validate_period(period: str) -> str:
    if period not in analytics.VALID_PERIODS:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unbekannte Periode '{period}'. "
                f"Erlaubt: {', '.join(analytics.VALID_PERIODS)}."
            ),
        )
    return period


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/top-sellers", response_model=list[TopSeller])
def top_sellers(
    period: str = _PeriodLiteral,
    limit: int = Query(20, ge=1, le=200),
    sort_by: str = Query(
        "qty",
        pattern="^(qty|revenue|margin)$",
        description="Sortierung: qty|revenue|margin",
    ),
    db: Session = Depends(get_db),
) -> list[TopSeller]:
    """Meistverkaufte Produkte im Zeitraum (default: letzte 30 Tage)."""
    _validate_period(period)
    rows = analytics.top_sellers(db, period=period, limit=limit, sort_by=sort_by)
    return [TopSeller.from_dc(r) for r in rows]


@router.get("/margins", response_model=list[MarginRow])
def margins(
    period: str = _PeriodLiteral,
    limit: int = Query(50, ge=1, le=500),
    only_with_sales: bool = Query(
        True,
        description="Wenn False, listet auch Produkte ohne Sales (Marge = 0).",
    ),
    db: Session = Depends(get_db),
) -> list[MarginRow]:
    """Marge pro Produkt im Zeitraum — nach absoluter Marge sortiert."""
    _validate_period(period)
    rows = analytics.margins(
        db, period=period, limit=limit, only_with_sales=only_with_sales
    )
    return [MarginRow.from_dc(r) for r in rows]


@router.get("/dead-stock", response_model=list[DeadStockRow])
def dead_stock(
    period: str = _PeriodLiteral,
    limit: int = Query(100, ge=1, le=500),
    include_zero_stock: bool = Query(
        True,
        description="Wenn False, werden Produkte mit Bestand = 0 ausgeblendet.",
    ),
    db: Session = Depends(get_db),
) -> list[DeadStockRow]:
    """Ladenhüter: aktive Produkte ohne jeden Verkauf im Zeitraum."""
    _validate_period(period)
    rows = analytics.dead_stock(
        db,
        period=period,
        limit=limit,
        include_zero_stock=include_zero_stock,
    )
    return [DeadStockRow.from_dc(r) for r in rows]


@router.get("/expiry-alerts", response_model=list[ExpiryAlert])
def expiry_alerts(
    warn_days: int = Query(
        analytics.DEFAULT_EXPIRY_WARN_DAYS,
        ge=1,
        le=365,
        description="Schwellwert in Tagen — Produkte mit MHD innerhalb dieses "
        "Fensters bekommen severity='warn'.",
    ),
    include_expired: bool = Query(True),
    limit: int = Query(200, ge=1, le=1000),
    db: Session = Depends(get_db),
) -> list[ExpiryAlert]:
    """MHD-Warnungen — bald ablaufend und/oder abgelaufen."""
    rows = analytics.expiry_alerts(
        db,
        warn_days=warn_days,
        include_expired=include_expired,
        limit=limit,
    )
    return [ExpiryAlert.from_dc(r) for r in rows]


@router.get("/reorder-alerts", response_model=list[ReorderAlert])
def reorder_alerts(
    include_zero_min: bool = Query(
        False,
        description="Wenn True, werden auch Produkte mit min_stock_level=0 "
        "gewertet, sobald stock_quantity < 0 ist (sollte nicht vorkommen).",
    ),
    limit: int = Query(200, ge=1, le=1000),
    db: Session = Depends(get_db),
) -> list[ReorderAlert]:
    """Nachbestell-Vorschläge (Bestand unter Mindestbestand)."""
    rows = analytics.reorder_alerts(
        db, include_zero_min=include_zero_min, limit=limit
    )
    return [ReorderAlert.from_dc(r) for r in rows]


@router.get("/dashboard/summary", response_model=DashboardSummary)
def dashboard_summary(
    period: str = _PeriodLiteral,
    warn_days: int = Query(analytics.DEFAULT_EXPIRY_WARN_DAYS, ge=1, le=365),
    db: Session = Depends(get_db),
) -> DashboardSummary:
    """Aggregierte KPIs für die Dashboard-Ansicht."""
    _validate_period(period)
    obj = analytics.dashboard_summary(
        db, period=period, warn_days=warn_days
    )
    return DashboardSummary.from_dc(obj)


@router.get("/notifications", response_model=list[NotificationItem])
def notifications(
    period: str = _PeriodLiteral,
    warn_days: int = Query(analytics.DEFAULT_EXPIRY_WARN_DAYS, ge=1, le=365),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[NotificationItem]:
    """Aggregierte Notifications für UI-Badge / Banner.

    Reihenfolge: danger → warn → info.
    """
    _validate_period(period)
    notes = analytics.aggregate_notifications(
        db, period=period, warn_days=warn_days
    )[:limit]
    return [NotificationItem.model_validate(n) for n in notes]