from typing import Any

from celery.result import AsyncResult

from celery_app import celery_app


def get_task_status(task_id: str) -> dict[str, Any]:
    """Read task state and result metadata without exposing a public endpoint."""
    task_result = AsyncResult(task_id, app=celery_app)
    response: dict[str, Any] = {"task_id": task_id, "state": task_result.state}
    if task_result.successful():
        response["result"] = task_result.result
    elif task_result.failed():
        response["error"] = str(task_result.result)
    return response