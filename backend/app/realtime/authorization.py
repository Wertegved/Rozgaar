from uuid import UUID

from app.db.models.enums import UserRole
from app.realtime.models import RealtimeResourceScope, RealtimeSubject


class RealtimeAccessPolicy:
    """Derives recipient access from server-loaded relationships."""

    @staticmethod
    def can_receive(subject: RealtimeSubject, scope: RealtimeResourceScope) -> bool:
        if scope.admin_only:
            return subject.role is UserRole.ADMIN
        if subject.role is UserRole.ADMIN:
            return True
        if subject.user_id in scope.participant_user_ids:
            return True
        if scope.owner_user_id == subject.user_id or scope.worker_user_id == subject.user_id:
            return True
        return subject.role is UserRole.WORKER and scope.worker_discoverable

    @staticmethod
    def recipients(subjects: list[RealtimeSubject], scope: RealtimeResourceScope) -> frozenset[UUID]:
        return frozenset(subject.user_id for subject in subjects if RealtimeAccessPolicy.can_receive(subject, scope))