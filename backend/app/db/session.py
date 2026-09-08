from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings


def create_database_engine():
    database_url = get_settings().sqlalchemy_database_url
    if not database_url:
        return None
    return create_engine(database_url, pool_pre_ping=True)


engine = create_database_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db() -> Generator[Session, None, None]:
    if engine is None:
        raise RuntimeError("DATABASE_URL is required for database access")
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()