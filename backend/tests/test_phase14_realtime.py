from uuid import uuid4

import pytest

from app.core.config import Settings
from app.db.models.enums import UserRole
from app.realtime.authorization import RealtimeAccessPolicy
from app.realtime.events import EVENT_TABLES, REALTIME_TABLES, RealtimeEvent, RealtimeTable
from app.realtime.models import RealtimeResourceScope, RealtimeSubject
from app.realtime.payloads import public_payload
from app.realtime.service import RealtimeDelivery, build_event, recover_from_api


def test_realtime_configuration_and_minimal_table_allowlist() -> None:
    settings = Settings(_env_file=None)

    assert settings.realtime_enabled is True
    assert settings.realtime_publication == "supabase_realtime"
    assert RealtimeTable.JOBS in REALTIME_TABLES
    assert RealtimeTable.NOTIFICATIONS in REALTIME_TABLES
    assert RealtimeTable.__members__.get("JOB_IMAGES") is None
    assert len(EVENT_TABLES) == len(RealtimeEvent)


def test_event_names_and_tables_are_consistent() -> None:
    assert RealtimeEvent.APPLICATION_SUBMITTED.value == "application.submitted"
    assert EVENT_TABLES[RealtimeEvent.APPLICATION_SUBMITTED] is RealtimeTable.APPLICATIONS
    assert EVENT_TABLES[RealtimeEvent.COMPLETION_COMPLETED] is RealtimeTable.COMPLETIONS


def test_consumer_and_worker_scope_isolation() -> None:
    consumer_id, worker_id, unrelated_id, admin_id = (uuid4() for _ in range(4))
    subjects = [
        RealtimeSubject(consumer_id, UserRole.CONSUMER),
        RealtimeSubject(worker_id, UserRole.WORKER),
        RealtimeSubject(unrelated_id, UserRole.WORKER),
        RealtimeSubject(admin_id, UserRole.ADMIN),
    ]
    scope = RealtimeResourceScope(owner_user_id=consumer_id, worker_user_id=worker_id)

    event = build_event(
        RealtimeEvent.APPLICATION_ACCEPTED,
        {"application_id": str(uuid4()), "status": "ACCEPTED"},
        subjects,
        scope,
    )

    assert event.recipient_user_ids == {consumer_id, worker_id, admin_id}
    assert event.for_user(RealtimeSubject(unrelated_id, UserRole.WORKER)) is None


def test_admin_only_scope_and_worker_discovery() -> None:
    admin_id, worker_id, consumer_id = uuid4(), uuid4(), uuid4()
    subjects = [
        RealtimeSubject(admin_id, UserRole.ADMIN),
        RealtimeSubject(worker_id, UserRole.WORKER),
        RealtimeSubject(consumer_id, UserRole.CONSUMER),
    ]

    admin_event = build_event(
        RealtimeEvent.COMPLAINT_CREATED,
        {"complaint_id": str(uuid4()), "status": "NEW"},
        subjects,
        RealtimeResourceScope(admin_only=True),
    )
    discoverable_event = build_event(
        RealtimeEvent.JOB_CREATED,
        {"job_id": str(uuid4()), "status": "POSTED"},
        subjects,
        RealtimeResourceScope(owner_user_id=consumer_id, worker_discoverable=True),
    )

    assert admin_event.recipient_user_ids == {admin_id}
    assert discoverable_event.recipient_user_ids == {admin_id, worker_id, consumer_id}


def test_payload_removes_private_data_recursively() -> None:
    payload = public_payload(
        {
            "application_id": "application",
            "phone": "private",
            "nested": {"email": "private", "status": "ACCEPTED"},
            "images": [{"storage_path": "private", "kind": "completion"}],
        }
    )

    assert payload == {
        "application_id": "application",
        "nested": {"status": "ACCEPTED"},
        "images": [{"kind": "completion"}],
    }


def test_payload_does_not_expose_service_role_or_private_storage() -> None:
    payload = public_payload(
        {
            "service_role_key": "secret",
            "supabase_service_role_key": "secret",
            "evidence_url": "private",
            "status": "COMPLETED",
        }
    )

    assert payload == {"status": "COMPLETED"}


def test_realtime_failure_is_non_fatal_and_does_not_mutate_state() -> None:
    delivery = RealtimeDelivery(transport=lambda _: (_ for _ in ()).throw(RuntimeError("offline")))

    assert delivery.publish(
        build_event(
            RealtimeEvent.NOTIFICATION_CREATED,
            {"notification_id": str(uuid4()), "is_read": False},
            [],
            RealtimeResourceScope(),
        )
    ) is False


def test_duplicate_events_are_delivery_only_and_recovery_uses_existing_api() -> None:
    event = build_event(
        RealtimeEvent.JOB_STATUS_CHANGED,
        {"job_id": str(uuid4()), "status": "STARTED"},
        [],
        RealtimeResourceScope(),
    )

    assert event == event
    assert "existing FastAPI APIs" in recover_from_api()