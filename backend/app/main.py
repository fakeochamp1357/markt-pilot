"""MarktPilot — FastAPI App Entry-Point.

Phase 1 MVP: Mobile-first Preisliste & Warenbestand.
Lokal, offline-fähig, eine SQLite-Datei.
"""
from __future__ import annotations

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect, text

from app.db.session import Base, engine
from app.routers import categories, products, receipts, stock

# Modelle registrieren (müssen vor ``create_all`` importiert sein)
import app.models  # noqa: F401


# ---------------------------------------------------------------------------
# Schema-Migrations-Helfer
# ---------------------------------------------------------------------------
# Vor alembic-Umstellung hatten wir ``Base.metadata.create_all`` allein.
# Falls jemand die alte DB noch benutzt, koennen Spalten fehlen, die wir
# per Alembic-Migration hinzugefuegt haben. ``_ensure_schema_columns``
# versucht, die fehlenden Spalten per ALTER TABLE nachzuruesten.
#
# Idempotent: bereits vorhandene Spalten werden uebersprungen.
# ---------------------------------------------------------------------------
_LEGACY_COLUMN_HINTS: list[tuple[str, str, str, str | None]] = [
    # products-Tabelle: Pfand/Pack-Size (Migration b2c3d4e5f6a7)
    ("products", "deposit_cents", "INTEGER", "0"),
    ("products", "pieces_per_pack", "INTEGER", "1"),
    ("products", "pack_unit", "VARCHAR(20)", None),
    ("products", "pack_barcode", "VARCHAR(32)", None),
    # receipts-Tabelle: print_requested (Migration c1d2e3f4a5b6)
    ("receipts", "print_requested", "BOOLEAN", "1"),
]


def _ensure_schema_columns() -> None:
    """Prueft und ergaenzt Legacy-Spalten ohne alembic-Tracking.

    Liest per ``inspect`` die existierenden Spalten jeder Tabelle und
    versucht fehlende ALTER TABLE ADD COLUMN auszufuehren.
    """
    try:
        inspector = inspect(engine)
    except Exception:
        return  # Kein DB-Zugriff — Base.metadata.create_all hilft

    existing_cols_by_table: dict[str, set[str]] = {}
    for table, column, sqltype, default in _LEGACY_COLUMN_HINTS:
        if table not in existing_cols_by_table:
            try:
                existing_cols_by_table[table] = {
                    c["name"] for c in inspector.get_columns(table)
                }
            except Exception:
                # Tabelle existiert noch nicht — wird durch create_all angelegt
                existing_cols_by_table[table] = set()
        if column in existing_cols_by_table[table]:
            continue
        try:
            with engine.begin() as conn:
                conn.execute(
                    text(
                        f'ALTER TABLE "{table}" ADD COLUMN "{column}" {sqltype}'
                    )
                )
                if default is not None:
                    conn.execute(
                        text(
                            f'UPDATE "{table}" SET "{column}" = {default} '
                            f'WHERE "{column}" IS NULL'
                        )
                    )
            existing_cols_by_table[table].add(column)
            print(
                f'[startup] legacy schema: ADD COLUMN "{table}"."{column}" {sqltype}',
                flush=True,
            )
        except Exception as exc:
            print(
                f'[startup] legacy schema: could not ALTER {table}.{column}: {exc}',
                flush=True,
            )


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Auto-Create der Tabellen beim Start + Legacy-Spalten-Repair."""
    if os.environ.get("MARKTPILOT_SKIP_AUTO_CREATE", "").lower() not in (
        "1", "true", "yes"
    ):
        Base.metadata.create_all(bind=engine)
        _ensure_schema_columns()
    yield


app = FastAPI(
    title="MarktPilot API",
    description=(
        "MarktPilot — Supermarkt-POS/Warenbestand Backend. "
        "Phase 1 MVP: Produkte, Kategorien, Stock, Bulk-Import, Export."
    ),
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# CORS offen für Development — in Phase 3 härten.
_cors_origins = os.environ.get("CORS_ALLOW_ORIGINS", "*")
_origins_list: list[str] | str = (
    ["*"] if _cors_origins.strip() == "*"
    else [o.strip() for o in _cors_origins.split(",") if o.strip()]
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/healthz", tags=["meta"])
def healthz() -> dict[str, str]:
    """Health-Check — gibt 'ok' zurück, wenn der Prozess lebt."""
    return {"status": "ok"}


# Router mounten
app.include_router(products.router)
app.include_router(categories.router)
app.include_router(stock.router)
app.include_router(receipts.router)