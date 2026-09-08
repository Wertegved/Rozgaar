from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol


@dataclass(frozen=True)
class ProviderPaymentResult:
    success: bool
    reference: str
    message: str | None = None


class PaymentProvider(Protocol):
    def create_payment(self, amount: Decimal, metadata: dict[str, str]) -> ProviderPaymentResult:
        ...

    def verify_payment(self, reference: str) -> ProviderPaymentResult:
        ...

    def refund_payment(self, reference: str) -> ProviderPaymentResult:
        ...