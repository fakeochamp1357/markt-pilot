"""Tagesabschluss-Router (Z-Bericht, Kassenzaehlung, Tagessperre).

GET  /api/day-close                  : letzte Abschluesse
GET  /api/day-close/{cash_session}   : Z-Bericht (live oder eingefroren)
POST /api/day-close/{cash_session}   : Tag abschliessen und sperren
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas import DayCloseCreate, DayCloseSummary, ZReport
from app.services.day_close import (
    AlreadyClosedError,
    DayCloseError,
    close_day,
    list_closes,
    report_for,
)

router = APIRouter(prefix="/api/day-close", tags=["day-close"])

SessionPath = Path(..., min_length=1, max_length=40, description="Schicht, z.B. 2026-10-09")


@router.get("", response_model=list[DayCloseSummary])
def get_closes(
    limit: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
) -> list[DayCloseSummary]:
    return [DayCloseSummary.model_validate(c) for c in list_closes(db, limit)]


@router.get("/{cash_session}", response_model=ZReport)
def get_report(cash_session: str = SessionPath, db: Session = Depends(get_db)) -> ZReport:
    return report_for(db, cash_session)


@router.post("/{cash_session}", response_model=ZReport, status_code=201)
def post_close(
    payload: DayCloseCreate,
    cash_session: str = SessionPath,
    db: Session = Depends(get_db),
) -> ZReport:
    """Schliesst den Tag ab. Danach werden Bons auf diese Schicht abgelehnt."""
    try:
        return close_day(db, cash_session, payload)
    except AlreadyClosedError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except DayCloseError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except IntegrityError:
        # Paralleler Abschluss derselben Schicht
        db.rollback()
        raise HTTPException(
            status_code=409, detail=f"Tag {cash_session} ist bereits abgeschlossen."
        )
