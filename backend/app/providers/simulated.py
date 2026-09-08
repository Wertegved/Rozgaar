from decimal import Decimal
from uuid import uuid4

from app.providers.base import ProviderPaymentResult


class SimulatedPaymentProvider:
    def __init__(self, should_fail: bool = False) -> None:
        self.should_fail = should_fail

    def create_payment(self, amount: Decimal, metadata: dict[str, str]) -> ProviderPaymentResult:
        reference = f"SIM-{uuid4()}"
        if self.should_fail:
            return ProviderPaymentResult(False, reference, "Simulated payment failure")
        return ProviderPaymentResult(True, reference, "Simulated payment completed")

    def verify_payment(self, reference: str) -> ProviderPaymentResult:
        return ProviderPaymentResult(True, reference, "Simulated payment verified")

    def refund_payment(self, reference: str) -> ProviderPaymentResult:
        return ProviderPaymentResult(True, reference, "Simulated refund recorded")