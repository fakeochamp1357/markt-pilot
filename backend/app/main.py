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

from app.db.session import Base, engine
from app.routers import categories, products, receipts, stock

# Modelle registrieren (müssen vor ``create_all`` importiert sein)
import app.models  # noqa: F401


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Auto-Create der Tabellen beim Start (deaktivierbar via ENV)."""
    if os.environ.get("MARKTPILOT_SKIP_AUTO_CREATE", "").lower() not in (
        "1", "true", "yes"
    ):
        Base.metadata.create_all(bind=engine)
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