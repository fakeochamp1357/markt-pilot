"""Receipts-Router (POS / Kasse).

POST: erstellt einen Bon — idempotent via X-Client-Op-Id
GET : Liste / Detail / Storno
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Receipt
from app.schemas import ReceiptCreate, ReceiptRead
from app.services.idempotency import (
    CachedResponse,
    client_op_id_header,
    get_cached_response,
    record_response,
)
from app.services.receipts import (
    ReceiptError,
    TotalMismatchError,
    UnknownProductError,
    apply_receipt,
)

router = APIRouter(prefix="/api/receipts", tags=["receipts"])


@router.post("", response_model=ReceiptRead, status_code=201)
def create_receipt(
    payload: ReceiptCreate,
    db: Session = Depends(get_db),
    client_op_id: str | None = Depends(client_op_id_header),
) -> ReceiptRead:
    """Erstellt einen Kassenbon samt Stock-Mutationen.

    **Idempotenz**: derselbe ``X-Client-Op-Id`` liefert immer wieder den
    selben Bon — selbst wenn der Cashier nach WLAN-Crash nochmal auf
    "Bezahlen" tippt. KEIN doppelter Bestandsabzug.
    """
    # --- Idempotenz-Vorpruefung ---
    if client_op_id:
        cached = get_cached_response(db, client_op_id, "POST /api/receipts")
        if cached is not None:
            replay = CachedResponse(cached.response_json, cached.status_code)
            replay.raise_for_status()
            return ReceiptRead.model_validate(replay.body())
    # --- Ende Vorpruefung ---

    try:
        receipt = apply_receipt(db, payload)
    except TotalMismatchError as exc:
        if client_op_id:
            record_response(
                db,
                client_op_id=client_op_id,
                endpoint="POST /api/receipts",
                status_code=409,
                response_body={"detail": str(exc)},
            )
        raise HTTPException(status_code=409, detail=str(exc))
    except UnknownProductError as exc:
        if client_op_id:
            record_response(
                db,
                client_op_id=client_op_id,
                endpoint="POST /api/receipts",
                status_code=409,
                response_body={"detail": str(exc)},
            )
        raise HTTPException(status_code=409, detail=str(exc))
    except ReceiptError as exc:
        if client_op_id:
            record_response(
                db,
                client_op_id=client_op_id,
                endpoint="POST /api/receipts",
                status_code=400,
                response_body={"detail": str(exc)},
            )
        raise HTTPException(status_code=400, detail=str(exc))

    result = ReceiptRead.model_validate(receipt)
    if client_op_id:
        record_response(
            db,
            client_op_id=client_op_id,
            endpoint="POST /api/receipts",
            status_code=201,
            response_body=result.model_dump(mode="json"),
        )
    return result


@router.get("", response_model=list[ReceiptRead])
def list_receipts(
    cash_session: str | None = Query(None, description="Schicht-Filter"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> list[ReceiptRead]:
    stmt = select(Receipt)
    if cash_session is not None:
        stmt = stmt.where(Receipt.cash_session == cash_session)
    stmt = stmt.order_by(Receipt.created_at.desc()).limit(limit).offset(offset)
    rows = db.execute(stmt).scalars().all()
    return [ReceiptRead.model_validate(r) for r in rows]


@router.get("/{receipt_id}", response_model=ReceiptRead)
def get_receipt(receipt_id: int, db: Session = Depends(get_db)) -> ReceiptRead:
    receipt = db.get(Receipt, receipt_id)
    if receipt is None:
        raise HTTPException(status_code=404, detail="Bon nicht gefunden.")
    return ReceiptRead.model_validate(receipt)


@router.get("/by-number/{receipt_number}", response_model=ReceiptRead)
def get_receipt_by_number(
    receipt_number: str, db: Session = Depends(get_db)
) -> ReceiptRead:
    stmt = select(Receipt).where(Receipt.receipt_number == receipt_number)
    receipt = db.execute(stmt).scalar_one_or_none()
    if receipt is None:
        raise HTTPException(
            status_code=404, detail=f"Bon '{receipt_number}' nicht gefunden."
        )
    return ReceiptRead.model_validate(receipt)


@router.post("/{receipt_id}/void", response_model=ReceiptRead)
def void_receipt(
    receipt_id: int, db: Session = Depends(get_db)
) -> ReceiptRead:
    """Storniert einen Bon — erzeugt einen Gegenbon und stellt Bestand wieder her.

    Idempotenz: das ist eine Sondersetzung ohne client_op_id (Cashier
    storniert typischerweise einmalig). Bei Mehrfach-Aufruf bekommt
    der zweite Call 404 (Originalbon ist schon weg).
    """
    original = db.get(Receipt, receipt_id)
    if original is None:
        raise HTTPException(status_code=404, detail="Bon nicht gefunden.")
    if original.kind != "sale":
        raise HTTPException(
            status_code=400,
            detail=f"Nur Verkauf-Bons (kind='sale') koennen storniert werden, ist '{original.kind}'.",
        )

    # Storno-Bon bauen — Total negiert, Lines negiert.
    storno_payload = ReceiptCreate(
        kind="storno",
        original_receipt_id=original.id,
        cash_session=original.cash_session,
        payment_method=original.payment_method,
        tendered_cents=0,
        change_cents=0,
        total_cents=-original.total_cents,
        cashier_name=original.cashier_name,
        notes=f"Storno zu Bon {original.receipt_number}",
        print_requested=False,  # Storno wird nicht separat gedruckt
        lines=[
            {
                "kind": "storno",
                "product_id": line.product_id,
                "name_snapshot": line.name_snapshot,
                "unit_snapshot": line.unit_snapshot,
                "quantity": -line.quantity,
                "unit_price_cents": line.unit_price_cents,
                "line_total_cents": -line.line_total_cents,
                "comment": line.comment,
            }
            for line in original.lines
        ],
    )
    try:
        storno = apply_receipt(db, storno_payload)
    except (TotalMismatchError, UnknownProductError, ReceiptError) as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return ReceiptRead.model_validate(storno)
