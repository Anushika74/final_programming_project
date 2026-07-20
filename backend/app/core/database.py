"""Database engine, session factory and declarative base.

The engine is created from `settings.DATABASE_URL`, so SystemIQ works with
SQLite, PostgreSQL or MySQL without code changes.
"""
from __future__ import annotations

from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings

# SQLite needs a special flag to be usable across threads (FastAPI + background tasks).
_connect_args = {"check_same_thread": False} if settings.is_sqlite else {}

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=_connect_args,
    pool_pre_ping=True,
    future=True,
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
    class_=Session,
)


class Base(DeclarativeBase):
    """Declarative base shared by all ORM models."""


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a scoped database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create all tables. Used for dev/SQLite; production should use Alembic."""
    # Import models so they are registered on the metadata before create_all.
    from app import models  # noqa: F401  (side-effect import)

    Base.metadata.create_all(bind=engine)
