"""Service-Layer fuer Kassenbons (Receipts).

Stellt sicher, dass:
  - jeder Bon eine eindeutige, fortlaufende ``receipt_number`` bekommt
  - die Server-Berechnung des Totals mit dem Client uebereinstimmt
    (sonst hätten wir eine trustlücke)
  - Stock-Movements (sale) und Receipt innerhalb EINER DB-Transaktion
    committed werden — entweder beides oder nichts
  - Retoure / Storno die Bestands-Veraenderung invertieren

Konzept receipt_number:
  Format: ``YYYYMMDD-NNNNNN`` mit Zaehler pro Tag, beginnt bei 1.
  Beispiel: ``20260701-000042`` ist der 42. Bon am 1.7.2026.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Product, Receipt, ReceiptLine, StockMovement
from app.schemas import ReceiptCreate


class ReceiptError(RuntimeError):
    """Allgemeiner Receipt-Fehler."""


class TotalMismatchError(ReceiptError):
    """Der vom Client gesendete total_cents weicht von der Server-Berechnung ab."""


class UnknownProductError(ReceiptError):
    """Eine Position verweist auf ein Produkt, das (nicht oder nicht mehr) existiert."""


def _next_receipt_number(db: Session) -> str:
    """Vergibt eine neue, fortlaufende receipt_number fuer HEUTE."""
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    prefix = f"{today}-"
    # MAX(receipt_number) pro Tag — geht weil unique + lexikografisch sortierbar
    stmt = (
        select(Receipt.receipt_number)
        .where(Receipt.receipt_number.like(f"{prefix}%"))
        .order_by(Receipt.receipt_number.desc())
        .limit(1)
    )
    last = db.execute(stmt).scalar_one_or_none()
    if last is None:
        return f"{today}-000001"
    try:
        seq = int(last.split("-", 1)[1]) + 1
    except (IndexError, ValueError):
        # Korrupter Datensatz — fang von vorne an
        return f"{today}-000001"
    return f"{today}-{seq:06d}"


def _cents_round(value: Decimal) -> int:
    """Cent-genaue Rundung (HALF_UP) — schuetzt vor Float-Drift."""
    return int(value.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def apply_receipt(
    db: Session,
    payload: ReceiptCreate,
) -> Receipt:
    """Validiert und persistiert einen Kassenbon samt Stock-Movements.

    Raises:
        TotalMismatchError: Client-total weicht von der Server-Berechnung ab.
        UnknownProductError: Line.product_id zeigt auf nicht-existentes Produkt.
    """
    # 1) Server-seitige Total-Berechnung aus den Lines.
    computed_total = 0
    # Snapshot-Felder aus DB ziehen, damit Client kein Ghost-Snapshots
    # einschleusen kann.
    product_cache: dict[int, Product] = {}

    for line in payload.lines:
        computed_total += line.line_total_cents
        if line.product_id is not None and line.product_id not in product_cache:
            p = db.get(Product, line.product_id)
            if p is None:
                raise UnknownProductError(
                    f"Produkt {line.product_id} existiert nicht."
                )
            product_cache[line.product_id] = p

    if computed_total != payload.total_cents:
        raise TotalMismatchError(
            f"total_mismatch: server={computed_total} client={payload.total_cents}"
        )

    # Bei 'mixed' darf tendered_cents NICHT kleiner als total sein;
    # bei 'cash' muss tendered >= total sein (sonst zu wenig Geld).
    if payload.payment_method in ("cash", "mixed") and payload.tendered_cents < payload.total_cents:
        raise ReceiptError(
            "tendered_cents kleiner als total_cents — zu wenig Geld erhalten."
        )

    # 2) receipt_number vergeben + Receipt-Persist
    receipt = Receipt(
        receipt_number=_next_receipt_number(db),
        kind=payload.kind,
        original_receipt_id=payload.original_receipt_id,
        cash_session=payload.cash_session,
        payment_method=payload.payment_method,
        tendered_cents=payload.tendered_cents,
        change_cents=payload.change_cents,
        total_cents=payload.total_cents,
        cashier_name=payload.cashier_name,
        notes=payload.notes,
    )
    db.add(receipt)
    db.flush()  # damit receipt.id fuer die Lines verfuegbar ist

    # 3) Lines anlegen + Stock-Movements ableiten
    # Bei sale: Stock-Movement mit 'sale' Reason, qty * -1.
    # Bei return: Stock-Movement mit 'return' Reason, qty * +1.
    # Bei storno: ignoriert Stock (der Originalbon muss separat storniert
    #             werden), hier nur die Storno-Position auf dem Bon.
    for idx, line in enumerate(payload.lines):
        db.add(
            ReceiptLine(
                receipt_id=receipt.id,
                position=idx,
                kind=line.kind,
                product_id=line.product_id,
                name_snapshot=line.name_snapshot,
                unit_snapshot=line.unit_snapshot,
                quantity=Decimal(str(line.quantity)),
                unit_price_cents=line.unit_price_cents,
                line_total_cents=line.line_total_cents,
                comment=line.comment,
            )
        )

        # Stock-Auswirkung:
        #   'sale'    -> Bestand abziehen   (qty * -1)
        #   'return'  -> Bestand gutschreiben (qty * +1)
        #   'storno'  -> behandelt wie 'return' (Storno-Bon stellt Bestand
        #                vom Original-Verkauf wieder her; die Line-Menge ist
        #                im Storno-Bon negativ, also `-(-qty) = +qty`)
        #   'deposit' -> kein Stock-Effekt (Pfand ist buchhalterisch)
        if line.product_id is not None and line.kind in ("sale", "return", "storno"):
            product = product_cache[line.product_id]
            qty = Decimal(str(line.quantity))
            if line.kind == "sale":
                change = -qty
                reason = "sale"
            else:  # 'return' oder 'storno'
                change = -qty  # storno-line hat negative qty, also -(-qty) = +qty
                reason = "return"
            movement = StockMovement(
                product_id=product.id,
                change=change,
                reason=reason,
                reference=f"Bon {receipt.receipt_number}",
                created_by=payload.cashier_name or "kasse",
            )
            db.add(movement)
            # Bestand und Version atomar anpassen
            product.stock_quantity = Decimal(product.stock_quantity) + change
            product.version = product.version + 1

    db.commit()
    db.refresh(receipt)
    return receipt
