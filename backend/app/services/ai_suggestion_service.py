from app.ai.errors import AIProviderError
from app.ai.models import AIRequest
from app.ai.service import AIService
from app.schemas.ai import JobDescriptionAutocompleteRequest


SYSTEM_INSTRUCTION = (
    "You complete local-service job descriptions for a hiring platform. "
    "Continue the user's partial sentence naturally in at most 12 words. "
    "Do not repeat their text. Do not add quotes or explanations. "
    "If the input already reads as a complete thought, return an empty string."
)


def suggest_job_description_continuation(
    ai_service: AIService, data: JobDescriptionAutocompleteRequest
) -> str:
    prompt = (
        f"Category: {data.category or 'GENERAL'}\n"
        f"Title: {data.title}\n"
        f"Partial description: {data.partial_description}"
    )
    try:
        response = ai_service.generate(
            AIRequest(prompt=prompt, system_instruction=SYSTEM_INSTRUCTION)
        )
    except AIProviderError:
        return ""
    return response.content.strip()
