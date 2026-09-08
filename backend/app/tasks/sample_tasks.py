from celery_app import celery_app


@celery_app.task(
    bind=False,
    name="rozgaar.verify_task",
    ignore_result=False,
    autoretry_for=(),
)
def verify_task(value: str) -> str:
    """Return a deterministic result for verifying the worker pipeline."""
    if not isinstance(value, str):
        raise TypeError("value must be a string")
    return value.upper()