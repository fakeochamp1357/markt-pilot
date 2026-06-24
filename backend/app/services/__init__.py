"""Service-Layer für Produkt-Stock-Updates mit optimistic locking."""
from __future__ import annotations

from decimal import Decimal

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.models import Product, StockMovement


class StockUpdateError(RuntimeError):
    """Wird geworfen, wenn das optimistische Lock fehlschlägt."""


def apply_stock_movement(
    db: Session,
    *,
    product_id: int,
    change: Decimal,
    reason: str,
    reference: str | None,
    created_by: str | None,
) -> tuple[StockMovement, Product]:
    """Wendet einen Stock-Movement atomar an.

    Verwendet ein optimisches Lock (UPDATE ... WHERE id=? AND version=?) um
    Race-Conditions bei parallelen Verbuchungen zu verhindern.

    Returns: (StockMovement, aktualisiertes Product).
    Raises:
        StockUpdateError wenn das Produkt nicht existiert oder die Version
            nicht mehr stimmt (Retry möglich).
    """
    product = db.get(Product, product_id)
    if product is None:
        raise StockUpdateError(f"Produkt {product_id} existiert nicht.")

    expected_version = product.version
    new_qty = Decimal(product.stock_quantity) + Decimal(change)

    # CAS-Update: nur wenn die Version noch passt.
    result = db.execute(
        update(Product)
        .where(Product.id == product_id, Product.version == expected_version)
        .values(
            stock_quantity=new_qty,
            version=expected_version + 1,
        )
    )

    if result.rowcount != 1:
        # Version mismatch — ein anderer Prozess hat zwischenzeitlich
        # geschrieben. Aufrufer kann retry-en.
        db.rollback()
        raise StockUpdateError(
            f"Stock-Update Race-Condition für Produkt {product_id} "
            f"(expected version {expected_version})."
        )

    movement = StockMovement(
        product_id=product_id,
        change=Decimal(change),
        reason=reason,
        reference=reference,
        created_by=created_by,
    )
    db.add(movement)
    db.commit()
    db.refresh(product)
    db.refresh(movement)
    return movement, product