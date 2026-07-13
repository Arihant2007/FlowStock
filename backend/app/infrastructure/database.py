"""SQLAlchemy engine and async-session factory.

All database I/O uses synchronous SQLAlchemy sessions because:
  - Neon PostgreSQL on Render's free tier works well with sync drivers.
  - psycopg2 (sync) is well-tested and stable.
  - Async SQLAlchemy adds complexity without measurable gain at this scale.

Session dependency is exposed as `get_db` for FastAPI Depends injection.
"""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

settings = get_settings()

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,  # Detect stale connections before use.
    pool_size=10,
    max_overflow=20,
    echo=not settings.is_production,  # Log SQL in development only.
)

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


def get_db() -> Generator[Session, None, None]:
    """Yield a database session for use as a FastAPI dependency.

    Automatically closes the session after the request completes,
    regardless of whether an exception was raised.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
