import logging
from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

from app.core.config import get_settings

logger = logging.getLogger(__name__)


def create_database_engine(database_url: str | None = None):
    resolved_url = database_url or get_settings().sqlalchemy_database_url
    if not resolved_url:
        return None

    engine = create_engine(
        resolved_url,
        poolclass=NullPool,
        pool_pre_ping=True,
    )

    @event.listens_for(engine, "connect")
    def _log_connect(dbapi_connection, connection_record):
        logger.info("DB connection connected")

    @event.listens_for(engine, "checkout")
    def _log_checkout(dbapi_connection, connection_record, connection_proxy):
        logger.info("DB connection checked out")

    @event.listens_for(engine, "checkin")
    def _log_checkin(dbapi_connection, connection_record):
        logger.info("DB connection checked in")

    @event.listens_for(engine, "invalidate")
    def _log_invalidate(dbapi_connection, connection_record, exception):
        logger.warning("DB connection invalidated")

    return engine


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