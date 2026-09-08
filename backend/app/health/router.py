from fastapi import APIRouter


router = APIRouter(tags=["health"])


@router.get("/health", summary="Check application health", operation_id="health_check")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready", summary="Check application readiness", operation_id="readiness_check")
async def ready() -> dict[str, str]:
    return {"status": "ready"}