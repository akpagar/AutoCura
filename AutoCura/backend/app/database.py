"""
AutoCura - Database Setup

SQLAlchemy engine, session factory, and declarative base.
All ORM models (app/models/*.py) should inherit from `Base`.
"""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings

engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    future=True,
)

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    future=True,
)


class Base(DeclarativeBase):
    """Base class for all ORM models."""
    pass


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency that yields a database session and guarantees
    it is closed after the request, even if an exception is raised.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """
    Create all tables based on imported models.
    Call this at application startup (development convenience).
    For production, prefer a proper migration tool (e.g. Alembic).
    """
    # Import models here so they are registered on Base.metadata
    from app.models import alerts, decision, logs, metrics, prediction, recovery, user  # noqa: F401

    Base.metadata.create_all(bind=engine)
