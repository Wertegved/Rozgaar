from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings


def create_database_engine(database_url: str | None = None):
    resolved_url = database_url or get_settings().sqlalchemy_database_url
    if not resolved_url:
        return None
    return create_engine(
        resolved_url,
        pool_size=3,
        max_overflow=2,
        pool_timeout=30,
        pool_pre_ping=True,
        pool_recycle=1800,
    )


engine = create_database_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db() -> Generator[Session, None, None]:
    if engine is None:
        raise RuntimeError("DATABASE_URL is required for database access")
    session = SessionLocal()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()