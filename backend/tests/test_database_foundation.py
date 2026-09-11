from sqlalchemy import CheckConstraint, UniqueConstraint
from sqlalchemy.pool import NullPool

from app.core.config import Settings
from app.db.base import Base
from app.db.models import Application, Job, Review, WorkerSkill
from app.db.session import create_database_engine, get_db


def test_database_configuration_does_not_require_secrets() -> None:
    settings = Settings(_env_file=None)

    assert settings.database_url is None


def test_postgresql_driver_is_explicitly_selected() -> None:
    settings = Settings(database_url="postgresql://user:pass@localhost/db", _env_file=None)

    assert settings.sqlalchemy_database_url == "postgresql+psycopg://user:pass@localhost/db"


def test_expected_tables_are_registered() -> None:
    expected = {
        "users",
        "consumer_profiles",
        "worker_profiles",
        "skills",
        "worker_skills",
        "jobs",
        "job_images",
        "job_requirements",
        "applications",
        "negotiations",
        "agreements",
        "payments",
        "completions",
        "completion_evidence",
        "reviews",
        "complaints",
        "disputes",
        "dispute_messages",
        "cancellations",
    }

    assert expected.issubset(Base.metadata.tables)


def test_core_constraints_are_present() -> None:
    assert any(isinstance(item, UniqueConstraint) for item in Application.__table__.constraints)
    assert any(isinstance(item, CheckConstraint) for item in Job.__table__.constraints)
    assert any(isinstance(item, UniqueConstraint) for item in Review.__table__.constraints)
    assert any(isinstance(item, UniqueConstraint) for item in WorkerSkill.__table__.constraints)


def test_relationship_foreign_keys_are_present() -> None:
    job_consumer_fk = next(iter(Job.__table__.c.consumer_id.foreign_keys))

    assert job_consumer_fk.column.table.name == "consumer_profiles"
    assert Application.__table__.c.job_id.foreign_keys
    assert Application.__table__.c.worker_id.foreign_keys


def test_sqlalchemy_engine_uses_null_pool_for_production_session_pooler() -> None:
    engine = create_database_engine("postgresql://user:pass@db.example.com:5432/postgres")

    assert engine is not None
    assert isinstance(engine.pool, NullPool)
    assert engine.pool._pre_ping is True


def test_get_db_closes_sessions_after_request() -> None:
    session_generator = get_db()
    session = next(session_generator)

    assert session is not None
    assert session.bind is not None

    try:
        next(session_generator)
    except StopIteration:
        pass
    session_generator.close()