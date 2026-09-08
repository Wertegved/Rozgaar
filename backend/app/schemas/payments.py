from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.db.models.enums import PaymentStatus, PaymentType


class PaymentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    job_id: UUID
    agreement_id: UUID | None
    payer_id: UUID
    payee_id: UUID
    agreed_amount: Decimal
    advance_amount: Decimal
    final_amount: Decimal
    payment_type: PaymentType
    status: PaymentStatus
    transaction_reference: str | None
    created_at: datetime
    updated_at: datetime


class PaymentListResponse(BaseModel):
    items: list[PaymentResponse]
    simulated_transaction_value: Decimal


class PaymentFailureRequest(BaseModel):
    simulate_failure: bool = Field(default=False, description="Test-only simulated provider failure switch")