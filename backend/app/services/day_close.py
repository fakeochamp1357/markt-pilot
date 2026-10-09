"""Tagesabschluss (Z-Bericht) und Tagessperre.

Ablauf:
  1. ``build_report`` rechnet den Z-Bericht live aus den Bons einer Schicht.
  2. ``close_day`` vergleicht das gezaehlte Bargeld mit dem Soll, friert den
     Bericht als JSON ein und sperrt die Schicht. Danach lehnt
     ``apply_receipt`` jede weitere Buchung auf diese Schicht ab.

Soll-Bargeld = Anfangsbestand + Netto-Bareinnahmen (Bar-Verkaeufe minus
Bar-Stornos/-Retouren). Bons mit ``payment_method='mixed'`` speichern keine
Aufteilung und zaehlen daher nicht zum Soll-Bargeld; sie stehen separat
in der Zahlungsart-Uebersicht.
"""
from __future__ import annotations

import json
from collections import defaultdict
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import DayClose, Receipt
from app.schemas import (
    EURO_DENOMINATIONS_CENTS,
    DayCloseCreate,
    ZReport,
    ZReportPayment,
    ZReportVat,
)


class DayCloseError(RuntimeError):
    """Allgemeiner Fehler beim Tagesabschluss."""


class AlreadyClosedError(DayCloseError):
    """Die Schicht wurde bereits abgeschlossen."""


def _net_from_gross(gross_cents: int, vat_rate: int) -> int:
    net = Decimal(gross_cents) * 100 / Decimal(100 + vat_rate)
    return int(net.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def get_close(db: Session, cash_session: str) -> DayClose | None:
    stmt = select(DayClose).where(DayClose.cash_session == cash_session)
    return db.execute(stmt).scalar_one_or_none()


def build_report(db: Session, cash_session: str) -> ZReport:
    """Rechnet den Z-Bericht aus den aktuell gebuchten Bons (ohne Sperre)."""
    receipts = (
        db.execute(
            select(Receipt)
            .where(Receipt.cash_session == cash_session)
            .order_by(Receipt.receipt_number)
        )
        .scalars()
        .all()
    )

    counts = {"sale": 0, "storno": 0, "return": 0}
    storno_total = 0
    pay_total: dict[str, int] = defaultdict(int)
    pay_count: dict[str, int] = defaultdict(int)
    vat_gross: dict[int, int] = defaultdict(int)

    for r in receipts:
        counts[r.kind] = counts.get(r.kind, 0) + 1
        pay_total[r.payment_method] += r.total_cents
        if r.kind == "sale":
            pay_count[r.payment_method] += 1
        if r.kind == "storno":
            storno_total += -r.total_cents
        for line in r.lines:
            vat_gross[line.vat_rate] += line.line_total_cents

    by_payment = [
        ZReportPayment(
            payment_method=m,
            receipt_count=pay_count.get(m, 0),
            total_cents=pay_total[m],
        )
        for m in ("cash", "card", "mixed")
        if m in pay_total
    ]
    by_vat = []
    for rate in sorted(vat_gross, reverse=True):
        gross = vat_gross[rate]
        net = _net_from_gross(gross, rate)
        by_vat.append(
            ZReportVat(vat_rate=rate, gross_cents=gross, net_cents=net, vat_cents=gross - net)
        )

    return ZReport(
        cash_session=cash_session,
        closed=False,
        sale_count=counts["sale"],
        storno_count=counts["storno"],
        return_count=counts["return"],
        first_receipt_number=receipts[0].receipt_number if receipts else None,
        last_receipt_number=receipts[-1].receipt_number if receipts else None,
        total_cents=sum(r.total_cents for r in receipts),
        storno_total_cents=storno_total,
        by_payment=by_payment,
        by_vat=by_vat,
        cash_sales_cents=pay_total.get("cash", 0),
    )


def report_for(db: Session, cash_session: str) -> ZReport:
    """Eingefrorener Bericht fuer abgeschlossene Tage, sonst Live-Bericht."""
    close = get_close(db, cash_session)
    if close is not None:
        return ZReport.model_validate_json(close.report_json)
    return build_report(db, cash_session)


def _validate_denominations(payload: DayCloseCreate) -> None:
    if payload.denominations is None:
        return
    total = 0
    for key, count in payload.denominations.items():
        try:
            value = int(key)
        except ValueError:
            raise DayCloseError(f"Unbekannte Stueckelung '{key}'.")
        if value not in EURO_DENOMINATIONS_CENTS:
            raise DayCloseError(f"Unbekannte Stueckelung '{key}'.")
        if count < 0:
            raise DayCloseError("Anzahl im Zaehlprotokoll darf nicht negativ sein.")
        total += value * count
    if total != payload.counted_cash_cents:
        raise DayCloseError(
            f"Zaehlprotokoll ergibt {total} Cent, gemeldet wurden "
            f"{payload.counted_cash_cents} Cent."
        )


def close_day(db: Session, cash_session: str, payload: DayCloseCreate) -> ZReport:
    """Schliesst die Schicht ab und sperrt sie fuer weitere Buchungen.

    Raises:
        AlreadyClosedError: Fuer die Schicht existiert schon ein Abschluss.
        DayCloseError: Das Zaehlprotokoll passt nicht zum gezaehlten Betrag.
    """
    if get_close(db, cash_session) is not None:
        raise AlreadyClosedError(f"Tag {cash_session} ist bereits abgeschlossen.")
    _validate_denominations(payload)

    report = build_report(db, cash_session)
    expected = payload.opening_float_cents + report.cash_sales_cents
    last_z = db.execute(select(func.max(DayClose.z_number))).scalar_one_or_none() or 0

    close = DayClose(
        z_number=last_z + 1,
        cash_session=cash_session,
        opening_float_cents=payload.opening_float_cents,
        expected_cash_cents=expected,
        counted_cash_cents=payload.counted_cash_cents,
        difference_cents=payload.counted_cash_cents - expected,
        total_cents=report.total_cents,
        cashier_name=payload.cashier_name,
        notes=payload.notes,
        report_json="{}",
    )
    db.add(close)
    db.flush()  # closed_at-Default setzen

    report = report.model_copy(
        update={
            "closed": True,
            "z_number": close.z_number,
            "closed_at": close.closed_at,
            "cashier_name": close.cashier_name,
            "notes": close.notes,
            "opening_float_cents": close.opening_float_cents,
            "expected_cash_cents": close.expected_cash_cents,
            "counted_cash_cents": close.counted_cash_cents,
            "difference_cents": close.difference_cents,
            "denominations": payload.denominations,
        }
    )
    close.report_json = report.model_dump_json()
    db.commit()
    return report


def list_closes(db: Session, limit: int = 30) -> list[DayClose]:
    stmt = select(DayClose).order_by(DayClose.z_number.desc()).limit(limit)
    return list(db.execute(stmt).scalars().all())


__all__ = [
    "AlreadyClosedError",
    "DayCloseError",
    "build_report",
    "close_day",
    "get_close",
    "list_closes",
    "report_for",
]
