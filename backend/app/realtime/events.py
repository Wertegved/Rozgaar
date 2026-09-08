from enum import StrEnum


class RealtimeTable(StrEnum):
    JOBS = "jobs"
    APPLICATIONS = "applications"
    AGREEMENTS = "agreements"
    AVAILABILITY = "worker_availability"
    PAYMENTS = "payments"
    COMPLETIONS = "completions"
    COMPLETION_WORKER_STATES = "completion_worker_states"
    REVIEWS = "reviews"
    COMPLAINTS = "complaints"
    DISPUTES = "disputes"
    NOTIFICATIONS = "notifications"


class RealtimeEvent(StrEnum):
    JOB_CREATED = "job.created"
    JOB_UPDATED = "job.updated"
    JOB_STATUS_CHANGED = "job.status_changed"
    LOCATION_INTELLIGENCE_UPDATED = "location_intelligence.updated"
    APPLICATION_SUBMITTED = "application.submitted"
    APPLICATION_ACCEPTED = "application.accepted"
    APPLICATION_REJECTED = "application.rejected"
    APPLICATION_WITHDRAWN = "application.withdrawn"
    APPLICATION_COUNTER_OFFER = "application.counter_offer"
    AGREEMENT_CREATED = "agreement.created"
    AGREEMENT_UPDATED = "agreement.updated"
    AVAILABILITY_UPDATED = "availability.updated"
    PAYMENT_ADVANCE_COMPLETED = "payment.advance_completed"
    PAYMENT_FINAL_COMPLETED = "payment.final_completed"
    PAYMENT_FAILED = "payment.failed"
    COMPLETION_WORKER_CONFIRMED = "completion.worker_confirmed"
    COMPLETION_CONSUMER_CONFIRMED = "completion.consumer_confirmed"
    COMPLETION_COMPLETED = "completion.completed"
    REVIEW_CREATED = "review.created"
    COMPLAINT_CREATED = "complaint.created"
    COMPLAINT_UPDATED = "complaint.updated"
    COMPLAINT_RESOLVED = "complaint.resolved"
    DISPUTE_CREATED = "dispute.created"
    DISPUTE_UPDATED = "dispute.updated"
    DISPUTE_RESOLVED = "dispute.resolved"
    NOTIFICATION_CREATED = "notification.created"
    NOTIFICATION_READ = "notification.read"


EVENT_TABLES: dict[RealtimeEvent, RealtimeTable] = {
    RealtimeEvent.JOB_CREATED: RealtimeTable.JOBS,
    RealtimeEvent.JOB_UPDATED: RealtimeTable.JOBS,
    RealtimeEvent.JOB_STATUS_CHANGED: RealtimeTable.JOBS,
    RealtimeEvent.LOCATION_INTELLIGENCE_UPDATED: RealtimeTable.JOBS,
    RealtimeEvent.APPLICATION_SUBMITTED: RealtimeTable.APPLICATIONS,
    RealtimeEvent.APPLICATION_ACCEPTED: RealtimeTable.APPLICATIONS,
    RealtimeEvent.APPLICATION_REJECTED: RealtimeTable.APPLICATIONS,
    RealtimeEvent.APPLICATION_WITHDRAWN: RealtimeTable.APPLICATIONS,
    RealtimeEvent.APPLICATION_COUNTER_OFFER: RealtimeTable.APPLICATIONS,
    RealtimeEvent.AGREEMENT_CREATED: RealtimeTable.AGREEMENTS,
    RealtimeEvent.AGREEMENT_UPDATED: RealtimeTable.AGREEMENTS,
    RealtimeEvent.AVAILABILITY_UPDATED: RealtimeTable.AVAILABILITY,
    RealtimeEvent.PAYMENT_ADVANCE_COMPLETED: RealtimeTable.PAYMENTS,
    RealtimeEvent.PAYMENT_FINAL_COMPLETED: RealtimeTable.PAYMENTS,
    RealtimeEvent.PAYMENT_FAILED: RealtimeTable.PAYMENTS,
    RealtimeEvent.COMPLETION_WORKER_CONFIRMED: RealtimeTable.COMPLETIONS,
    RealtimeEvent.COMPLETION_CONSUMER_CONFIRMED: RealtimeTable.COMPLETIONS,
    RealtimeEvent.COMPLETION_COMPLETED: RealtimeTable.COMPLETIONS,
    RealtimeEvent.REVIEW_CREATED: RealtimeTable.REVIEWS,
    RealtimeEvent.COMPLAINT_CREATED: RealtimeTable.COMPLAINTS,
    RealtimeEvent.COMPLAINT_UPDATED: RealtimeTable.COMPLAINTS,
    RealtimeEvent.COMPLAINT_RESOLVED: RealtimeTable.COMPLAINTS,
    RealtimeEvent.DISPUTE_CREATED: RealtimeTable.DISPUTES,
    RealtimeEvent.DISPUTE_UPDATED: RealtimeTable.DISPUTES,
    RealtimeEvent.DISPUTE_RESOLVED: RealtimeTable.DISPUTES,
    RealtimeEvent.NOTIFICATION_CREATED: RealtimeTable.NOTIFICATIONS,
    RealtimeEvent.NOTIFICATION_READ: RealtimeTable.NOTIFICATIONS,
}


REALTIME_TABLES = frozenset(RealtimeTable)