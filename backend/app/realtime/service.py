import logging
from collections.abc import Callable

from app.realtime.authorization import RealtimeAccessPolicy
from app.realtime.events import EVENT_TABLES, RealtimeEvent
from app.realtime.models import RealtimeEventPayload, RealtimeResourceScope, RealtimeSubject
from app.realtime.payloads import public_payload


logger = logging.getLogger(__name__)


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
        self.transport = transport

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