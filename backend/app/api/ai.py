from fastapi import APIRouter, Depends

from app.ai.service import AIService
from app.auth.dependencies import require_consumer
from app.infrastructure.redis import consume_rate_limit
from app.schemas.ai import (
    JobDescriptionAutocompleteRequest,
    JobDescriptionAutocompleteResponse,
)
from app.services.ai_suggestion_service import suggest_job_description_continuation


router = APIRouter(prefix="/ai", tags=["ai"])


def get_ai_service() -> AIService:
    return AIService()


@router.post(
    "/job-description-autocomplete",
    response_model=JobDescriptionAutocompleteResponse,
)
def job_description_autocomplete(
    data: JobDescriptionAutocompleteRequest,
    user=Depends(require_consumer),
    ai_service: AIService = Depends(get_ai_service),
) -> JobDescriptionAutocompleteResponse:
    if not consume_rate_limit(
        f"ai-autocomplete:user:{user.id}",
        limit=30,
        window_seconds=60,
        fail_closed=True,
    ):
        return JobDescriptionAutocompleteResponse(suggestion="")
    suggestion = suggest_job_description_continuation(ai_service, data)
    return JobDescriptionAutocompleteResponse(suggestion=suggestion)
