from app.core.config import Settings
from app.tasks.sample_tasks import verify_task
from celery_app import celery_app


def test_redis_and_celery_configuration_defaults() -> None:
    settings = Settings(_env_file=None)

    assert settings.redis_url == "redis://localhost:6379/0"
    assert settings.celery_broker_url == "redis://localhost:6379/0"
    assert settings.celery_result_backend == "redis://localhost:6379/1"


def test_redis_and_celery_configuration_reads_environment(monkeypatch) -> None:
    monkeypatch.setenv("REDIS_URL", "redis://redis.example/2")
    monkeypatch.setenv("CELERY_BROKER_URL", "redis://broker.example/3")
    monkeypatch.setenv("CELERY_RESULT_BACKEND", "redis://results.example/4")

    settings = Settings(_env_file=None)

    assert settings.redis_url == "redis://redis.example/2"
    assert settings.celery_broker_url == "redis://broker.example/3"
    assert settings.celery_result_backend == "redis://results.example/4"


def test_celery_uses_settings_and_safe_serialization() -> None:
    assert celery_app.conf.broker_url == "redis://localhost:6379/0"
    assert celery_app.conf.result_backend == "redis://localhost:6379/1"
    assert celery_app.conf.task_serializer == "json"
    assert celery_app.conf.result_serializer == "json"
    assert celery_app.conf.accept_content == ["json"]
    assert celery_app.conf.task_always_eager is False


def test_verification_task_is_registered_and_deterministic() -> None:
    assert celery_app.tasks["rozgaar.verify_task"].name == verify_task.name

    result = verify_task.apply(args=["phase-14"])

    assert result.successful()
    assert result.result == "PHASE-14"


def test_verification_task_failure_is_observable() -> None:
    result = verify_task.apply(args=[None])

    assert result.failed()
    assert isinstance(result.result, TypeError)