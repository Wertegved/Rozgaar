from celery import Celery

from app.core.config import get_settings


settings = get_settings()

celery_app = Celery(
	"rozgaar",
	broker=settings.celery_broker_url,
	backend=settings.celery_result_backend,
	include=["app.tasks.sample_tasks"],
)
celery_app.conf.update(
	accept_content=["json"],
	task_serializer="json",
	result_serializer="json",
	enable_utc=True,
	timezone="UTC",
	task_track_started=True,
	task_acks_late=True,
	task_reject_on_worker_lost=True,
	worker_prefetch_multiplier=1,
	task_always_eager=False,
)

celery = celery_app
