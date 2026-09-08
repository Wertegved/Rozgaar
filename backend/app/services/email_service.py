import logging

from app.core.config import get_settings
from app.providers.email import EmailMessageData, EmailProvider, FakeEmailProvider, SMTPEmailProvider


logger = logging.getLogger(__name__)


class EmailService:
    def __init__(self, provider: EmailProvider | None = None) -> None:
        self.last_error: Exception | None = None
        if provider is not None:
            self.provider = provider
            return
        provider_name = get_settings().email_provider
        if provider_name == "fake":
            self.provider = FakeEmailProvider()
        elif provider_name == "smtp":
            self.provider = SMTPEmailProvider()
        else:
            raise ValueError(f"Unsupported EMAIL_PROVIDER: {provider_name}")

    def send(self, recipient: str | None, subject: str, body: str) -> bool:
        if not recipient:
            return False
        try:
            sent = self.provider.send(EmailMessageData(recipient, subject, body))
            self.last_error = None
            return sent
        except Exception as error:
            self.last_error = error
            logger.warning("Transactional email delivery failed: %s", type(error).__name__)
            return False