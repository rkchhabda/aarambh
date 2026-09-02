"""Database engine and session management — SQLite for simplicity, upgradeable to PostgreSQL."""

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "sqlite:///service/aarambh.db",
)

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {},
    pool_pre_ping=True,
    echo=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

_initialized = False


def get_db():
    """FastAPI dependency — yields a DB session and ensures cleanup."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Create all tables if they don't exist. Safe to call multiple times."""
    global _initialized
    if _initialized:
        return
    import service.models_db  # noqa: F401 — registers models with Base
    Base.metadata.create_all(bind=engine)
    _initialized = True
    print("[OK] Database initialized")


def ensure_db():
    """Ensure DB is initialized — called at module level and at startup."""
    init_db()
