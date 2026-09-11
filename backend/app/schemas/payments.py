from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

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


class SimulatedCardRequest(BaseModel):
    cardholder_name: str = Field(min_length=1, max_length=200)
    card_number: str = Field(min_length=16, max_length=23)
    expiry_month: int = Field(ge=1, le=12)
    expiry_year: int = Field(ge=2000, le=2200)
    cvv: str = Field(min_length=3, max_length=3)

    @field_validator("cardholder_name")
    @classmethod
    def validate_cardholder_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Cardholder name is required")
        return value

    @field_validator("card_number")
    @classmethod
    def validate_card_number(cls, value: str) -> str:
        normalized = value.replace(" ", "").replace("-", "")
        if not normalized.isdigit() or len(normalized) != 16 or sum(int(item) for item in normalized) % 10:
            raise ValueError("Card number must be 16 digits with a digit sum divisible by 10")
        return normalized

    @field_validator("cvv")
    @classmethod
    def validate_cvv(cls, value: str) -> str:
        if not value.isdigit() or len(value) != 3:
            raise ValueError("CVV must be exactly 3 digits")
        return value


class PaymentFailureRequest(BaseModel):
    simulate_failure: bool = Field(default=False, description="Test-only simulated provider failure switch")