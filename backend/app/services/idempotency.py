"""Idempotenz-Layer für POST-Endpoints.

Der Client (MarktPilot-Outbox) hängt an jeden Outbox-Eintrag eine client-
seitig generierte UUID (``X-Client-Op-Id``-Header). Wenn ein Request wiederholt
gesendet wird (z.B. nach WLAN-Crash), soll das Backend **nicht** ein zweites
Objekt anlegen, sondern die ursprüngliche Antwort 1:1 zurückgeben.

Dazu wird in der Tabelle ``processed_ops`` pro ``client_op_id`` die erste
Antwort gespeichert. Folge-Requests mit derselben ID lesen den Cache und
antworten identisch.

Wichtige Eigenschaften
- **Header ist optional**: ohne ``X-Client-Op-Id`` verhält sich der Endpoint
  exakt wie vorher (kein Dedup, jeder Call erzeugt ein neues Objekt).
  Bestehende Clients (z.B. das Swagger-UI) arbeiten weiter.
- **Statuscode wird mit gespeichert**: ein 4xx-Cache-Eintrag wird beim Retry
  ebenfalls 4xx zurückgeben — der Client sieht "wurde abgelehnt" und
  markiert den Outbox-Eintrag als terminal-failed, statt endlos zu retry-en.
- **5xx-Antworten werden NICHT gecached**: das wären echte Fehler, bei denen
  der Client retry-en soll. Wir persistieren den Eintrag erst bei Erfolg
  (2xx) oder bei semantisch klaren 4xx.
"""
from __future__ import annotations

import json
from typing import Any

from fastapi import Header, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import ProcessedOp

# Statuscodes, die wir für Retries wiederverwenden.
# 2xx → Erfolg, idempotent wiederverwendbar.
# 4xx → Client-Fehler (z.B. barcode vergeben, version mismatch), idempotent
#       wiederverwendbar — der Client soll den Outbox-Eintrag als failed
#       markieren, nicht weiter retry-en.
# 5xx → Server-Fehler, transient — wir cachen NICHT, damit der Client
#       weiter retry-en kann (z.B. DB-Lock).
CACHEABLE_STATUS_CODES = frozenset(range(200, 500))  # 2xx und 4xx


def _extract_client_op_id(
    x_client_op_id: str | None = Header(default=None, alias="X-Client-Op-Id"),
) -> str | None:
    """FastAPI-Dependency: liest den optionalen Idempotenz-Header.

    Liefert ``None`` wenn nicht gesetzt — der Endpoint läuft dann im
    "Legacy"-Modus ohne Dedup.
    """
    if x_client_op_id is None:
        return None
    cleaned = x_client_op_id.strip()
    if not cleaned:
        return None
    if len(cleaned) > 64:
        raise HTTPException(
            status_code=400,
            detail="X-Client-Op-Id zu lang (max 64 Zeichen).",
        )
    return cleaned


# Convenience-Alias für FastAPI Depends()-Aufrufe.
client_op_id_header = _extract_client_op_id


def get_cached_response(
    db: Session, client_op_id: str, endpoint: str
) -> ProcessedOp | None:
    """Liest den gecachten Response, falls vorhanden."""
    stmt = select(ProcessedOp).where(
        ProcessedOp.client_op_id == client_op_id,
        ProcessedOp.endpoint == endpoint,
    )
    return db.execute(stmt).scalar_one_or_none()


def record_response(
    db: Session,
    *,
    client_op_id: str,
    endpoint: str,
    status_code: int,
    response_body: Any,
) -> ProcessedOp | None:
    """Persistiert die Response für spätere Retries.

    Liefert ``None`` wenn der Statuscode nicht gecached werden soll (5xx).
    Bei einem Unique-Constraint-Konflikt (paralleler Retry mit derselben ID)
    wird der vorhandene Eintrag zurückgegeben — kein Fehler.
    """
    if status_code not in CACHEABLE_STATUS_CODES:
        return None

    if isinstance(response_body, (dict, list)):
        body_json = json.dumps(response_body, default=str, ensure_ascii=False)
    else:
        body_json = str(response_body)

    # Truncate defensively — sollte eigentlich nie passieren, aber die
    # Spalte ist 2000 Zeichen breit.
    if len(body_json) > 1900:
        body_json = body_json[:1900]

    entry = ProcessedOp(
        client_op_id=client_op_id,
        endpoint=endpoint,
        status_code=status_code,
        response_json=body_json,
    )
    db.add(entry)
    try:
        db.commit()
    except IntegrityError:
        # Parallel-Retry hat den Eintrag zuerst angelegt — wir nehmen den
        # vorhandenen und geben ihn zurück.
        db.rollback()
        return get_cached_response(db, client_op_id, endpoint)
    db.refresh(entry)
    return entry


class CachedResponse:
    """Hilfsobjekt: liest einen gecachten Response und macht ihn nutzbar.

    Verwendung im Endpoint:
        if client_op_id:
            cached = get_cached_response(db, client_op_id, ENDPOINT)
            if cached is not None:
                cached.raise_for_status_or_return_body()  # raise 4xx oder JSON
                # bei 2xx: als dict zurück
    """

    def __init__(self, raw_json: str, status_code: int) -> None:
        self._raw_json = raw_json
        self._status_code = status_code
        self._body: Any | None = None

    def body(self) -> Any:
        if self._body is None:
            try:
                self._body = json.loads(self._raw_json)
            except json.JSONDecodeError:
                self._body = {}
        return self._body

    def status_code(self) -> int:
        return self._status_code

    def raise_for_status(self) -> None:
        """Wirft HTTPException, wenn der gecachte Status 4xx war."""
        if 400 <= self._status_code < 500:
            body = self.body()
            detail = body.get("detail") if isinstance(body, dict) else None
            raise HTTPException(
                status_code=self._status_code,
                detail=detail or "Wiederverwendete Fehlerantwort.",
            )
