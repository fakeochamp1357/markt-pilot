"""Pytest fixtures — frische File-SQLite pro Test.

Warum File statt :memory:?
- SQLite `:memory:` ist pro Connection isoliert. Mit TestClient (verschiedene
  Threads/Connections je Request) würde jede Connection eine leere DB sehen.
- Stattdessen nutzen wir eine eindeutige Temp-Datei pro Test, die danach
  aufgeräumt wird.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

# Setze DATABASE_URL VOR allen app-Imports, damit die Session die
# In-Memory-DB verwendet. Wir überschreiben das aber gleich pro Test.
os.environ["MARKTPILOT_SKIP_AUTO_CREATE"] = "1"

from decimal import Decimal  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from app.db.session import Base, get_db  # noqa: E402
import app.models  # noqa: E402,F401  — registriert Tabellen
from app.main import app as fastapi_app  # noqa: E402


@pytest.fixture()
def engine():
    """Frische File-SQLite pro Test."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    db_path = f"sqlite:///{path}"
    eng = create_engine(
        db_path,
        connect_args={"check_same_thread": False},
        future=True,
    )
    Base.metadata.create_all(bind=eng)
    yield eng
    eng.dispose()
    Path(path).unlink(missing_ok=True)


@pytest.fixture()
def session_factory(engine):
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@pytest.fixture()
def db_session(session_factory):
    s = session_factory()
    try:
        yield s
    finally:
        s.close()


@pytest.fixture()
def client(session_factory):
    """TestClient mit überschriebener get_db-Dependency."""

    def _override_get_db():
        s = session_factory()
        try:
            yield s
        finally:
            s.close()

    fastapi_app.dependency_overrides[get_db] = _override_get_db
    with TestClient(fastapi_app) as c:
        yield c
    fastapi_app.dependency_overrides.clear()


@pytest.fixture()
def sample_product_payload():
    return {
        "sku": "TEST-001",
        "barcode": "4006381333931",
        "name": "Pilot Kugelschreiber",
        "unit": "Stück",
        "size_weight": "Standard",
        "cost_price": Decimal("0.50"),
        "sell_price": Decimal("1.49"),
        "currency": "EUR",
        "stock_quantity": Decimal("20"),
        "min_stock_level": Decimal("5"),
        "color_tag": "#3B82F6",
        "is_active": True,
    }