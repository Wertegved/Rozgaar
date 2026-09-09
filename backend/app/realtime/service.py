import logging
from collections.abc import Callable

import httpx
from fastapi.encoders import jsonable_encoder

from app.db.models.enums import UserRole
from app.realtime.authorization import RealtimeAccessPolicy
from app.realtime.events import EVENT_TABLES, RealtimeEvent
from app.realtime.models import RealtimeEventPayload, RealtimeResourceScope, RealtimeSubject
from app.realtime.payloads import public_payload


logger = logging.getLogger(__name__)


def supabase_broadcast_transport(event: RealtimeEventPayload) -> None:
    from app.core.config import get_settings

    settings = get_settings()
    if not settings.supabase_url or not settings.supabase_service_role_key:
        return

    messages = []
    for recipient_id in event.recipient_user_ids:
        recipient_payload = event.for_user(RealtimeSubject(recipient_id, UserRole.ADMIN))
        if recipient_payload is None:
            continue
        messages.append(
            {
                "topic": f"user:{recipient_id}",
                "event": "rozgaar.event",
                "payload": jsonable_encoder(recipient_payload),
            }
        )
    if not messages:
        return

    response = httpx.post(
        f"{settings.supabase_url.rstrip('/')}/realtime/v1/api/broadcast",
        headers={
            "Authorization": f"Bearer {settings.supabase_service_role_key}",
            "Content-Type": "application/json",
        },
        json={"messages": messages},
        timeout=5,
    )
    response.raise_for_status()


def build_event(
    event: RealtimeEvent,
    values: dict[str, object],
    subjects: list[RealtimeSubject],
    scope: RealtimeResourceScope,
    correlation_id: str | None = None,
) -> RealtimeEventPayload:
    """Build an allowlisted, recipient-scoped event from trusted server data."""
    recipient_ids = RealtimeAccessPolicy.recipients(subjects, scope)
    return RealtimeEventPayload(
        event=event,
        table=EVENT_TABLES[event],
        payload=public_payload(values),
        recipient_user_ids=recipient_ids,
        correlation_id=correlation_id,
    )


class RealtimeDelivery:
    """Best-effort delivery hook; database mutations never depend on it."""

    def __init__(self, transport: Callable[[RealtimeEventPayload], None] | None = None) -> None:
        self.transport = transport if transport is not None else supabase_broadcast_transport

    def publish(self, event: RealtimeEventPayload) -> bool:
        logger.info("realtime event prepared: %s on %s", event.event.value, event.table.value)
        if self.transport is None:
            return True
        try:
            self.transport(event)
            return True
        except Exception:
            logger.warning("realtime delivery failed for %s", event.event.value, exc_info=True)
            return False


def recover_from_api() -> str:
    """Document the recovery contract for clients after reconnect or missed events."""
    return "Fetch current authorized state through the existing FastAPI APIs."