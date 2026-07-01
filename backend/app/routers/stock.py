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
from app.services.idempotency import (
    CachedResponse,
    client_op_id_header,
    get_cached_response,
    record_response,
)

router = APIRouter(prefix="/api/stock", tags=["stock"])


@router.post("/movements", response_model=StockMovementRead, status_code=201)
def create_movement(
    payload: StockMovementCreate,
    db: Session = Depends(get_db),
    client_op_id: str | None = Depends(client_op_id_header),
) -> StockMovementRead:
    """Verbucht eine Stock-Bewegung.

    Atomar via optimistischem Lock (Version-CAS). Doppelte parallele Calls
    werden sauber serialisiert; bei Race-Condition gibt es einen 409-Response.

    **Idempotenz**: mit ``X-Client-Op-Id``-Header wird der erste Erfolg
    gecached. Wiederholte Calls mit derselben ID liefern die ursprüngliche
    Movement-ID zurück, ohne den Bestand erneut zu verändern. KRITISCH für
    die Kasse: ein Retry nach WLAN-Crash darf den Bestand nicht doppelt
    abbuchen.
    """
    # --- Idempotenz ---
    if client_op_id:
        cached = get_cached_response(db, client_op_id, "POST /api/stock/movements")
        if cached is not None:
            replay = CachedResponse(cached.response_json, cached.status_code)
            replay.raise_for_status()
            return StockMovementRead.model_validate(replay.body())
    # --- Ende Idempotenz-Vorprüfung ---

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
        # 409 cachen — sonst würde der Client bei einem fehlgeschlagenen
        # CAS-Update endlos retry-en und immer wieder 409 bekommen.
        if client_op_id:
            record_response(
                db,
                client_op_id=client_op_id,
                endpoint="POST /api/stock/movements",
                status_code=409,
                response_body={"detail": str(exc)},
            )
        raise HTTPException(status_code=409, detail=str(exc))

    result = StockMovementRead.model_validate(movement)
    if client_op_id:
        record_response(
            db,
            client_op_id=client_op_id,
            endpoint="POST /api/stock/movements",
            status_code=201,
            response_body=result.model_dump(mode="json"),
        )
    return result


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