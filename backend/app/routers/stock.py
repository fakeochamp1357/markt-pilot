"""Stock-Router: Bewegungen, Low-Stock, MHD."""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Product, StockMovement
from app.schemas import (
    ExpiringProduct,
    LowStockProduct,
    StockMovementCreate,
    StockMovementList,
    StockMovementRead,
)
from app.services import StockUpdateError, apply_stock_movement

router = APIRouter(prefix="/api/stock", tags=["stock"])


@router.post("/movements", response_model=StockMovementRead, status_code=201)
def create_movement(
    payload: StockMovementCreate,
    db: Session = Depends(get_db),
) -> StockMovementRead:
    """Verbucht eine Stock-Bewegung.

    Atomar via optimistischem Lock (Version-CAS). Doppelte parallele Calls
    werden sauber serialisiert; bei Race-Condition gibt es einen 409-Response.
    """
    try:
        movement, _ = apply_stock_movement(
            db,
            product_id=payload.product_id,
            change=Decimal(str(payload.change)),
            reason=payload.reason,
            reference=payload.reference,
            created_by=payload.created_by,
        )
    except StockUpdateError as exc:
        raise HTTPException(status_code=409, detail=str(exc))

    return StockMovementRead.model_validate(movement)


@router.get("/movements", response_model=StockMovementList)
def list_movements(
    product_id: int | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> StockMovementList:
    stmt = select(StockMovement)
    if product_id is not None:
        stmt = stmt.where(StockMovement.product_id == product_id)
    total = db.execute(
        select(func.count()).select_from(stmt.subquery())
    ).scalar_one()
    stmt = stmt.order_by(StockMovement.created_at.desc()).limit(limit).offset(offset)
    rows = db.execute(stmt).scalars().all()
    return StockMovementList(
        items=[StockMovementRead.model_validate(m) for m in rows],
        total=total,
    )


@router.get("/low", response_model=list[LowStockProduct])
def low_stock(
    db: Session = Depends(get_db),
) -> list[LowStockProduct]:
    """Produkte, deren Bestand unter min_stock_level liegt."""
    stmt = (
        select(Product)
        .where(
            Product.is_active.is_(True),
            Product.min_stock_level > 0,
            Product.stock_quantity < Product.min_stock_level,
        )
        .order_by(Product.stock_quantity.asc())
    )
    rows = db.execute(stmt).scalars().all()
    return [LowStockProduct.from_orm(p) for p in rows]


@router.get("/expiring", response_model=list[ExpiringProduct])
def expiring(
    days: int = Query(30, ge=0, le=365),
    db: Session = Depends(get_db),
) -> list[ExpiringProduct]:
    """Produkte mit MHD innerhalb der nächsten ``days`` Tage."""
    today = date.today()
    cutoff = today + timedelta(days=days)
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
    return [ExpiringProduct.from_orm(p, today) for p in rows]