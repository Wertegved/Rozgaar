from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from app.db.models.enums import UserRole
from app.realtime.events import RealtimeEvent, RealtimeTable


@dataclass(frozen=True)
class RealtimeSubject:
    user_id: UUID
    role: UserRole


@dataclass(frozen=True)
class RealtimeResourceScope:
    """Trusted relationship data loaded by FastAPI, never supplied by clients."""

    owner_user_id: UUID | None = None
    worker_user_id: UUID | None = None
    participant_user_ids: frozenset[UUID] = frozenset()
    admin_only: bool = False
    worker_discoverable: bool = False


@dataclass(frozen=True)
class RealtimeEventPayload:
    event: RealtimeEvent
    table: RealtimeTable
    payload: dict[str, Any]
    recipient_user_ids: frozenset[UUID] = frozenset()
    correlation_id: str | None = None

    def for_user(self, subject: RealtimeSubject) -> dict[str, Any] | None:
        if subject.user_id not in self.recipient_user_ids:
            return None
        from app.realtime.payloads import public_payload

        return {
            "event": self.event.value,
            "table": self.table.value,
            "payload": public_payload(self.payload),
            **({"correlation_id": self.correlation_id} if self.correlation_id else {}),
        }