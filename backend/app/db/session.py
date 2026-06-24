"""Database engine, session, and base setup.

MarktPilot — Phase 1 MVP
- SQLite file-based DB (lokal-first, offline-fähig)
- SQLAlchemy 2.x ORM
"""
from __future__ import annotations

import os
from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

# Default to a local SQLite file next to the backend/ dir.
DEFAULT_DB_URL = "sqlite:///./markt_pilot.db"
DATABASE_URL = os.environ.get("DATABASE_URL", DEFAULT_DB_URL)

# SQLite needs `check_same_thread=False` when used from multiple threads
# (uvicorn workers etc.). In-memory DB (used by tests) gets the same flag.
_connect_args = {"check_same_thread": False}

engine = create_engine(
    DATABASE_URL,
    echo=False,
    future=True,
    connect_args=_connect_args,
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
    class_=Session,
)


class Base(DeclarativeBase):
    """SQLAlchemy 2.x declarative base."""

    pass


def get_db() -> Iterator[Session]:
    """FastAPI dependency that yields a session and closes it afterwards."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()