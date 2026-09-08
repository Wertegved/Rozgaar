from dataclasses import dataclass, field
from email.message import EmailMessage
import smtplib

from app.core.config import get_settings


class EmailConfigurationError(RuntimeError):
    """Raised when SMTP is explicitly selected but is not configured."""


@dataclass(frozen=True)
class EmailMessageData:
    recipient: str
    subject: str
    body: str
    html_body: str | None = None


class EmailProvider:
    def send(self, message: EmailMessageData) -> bool:
        raise NotImplementedError


@dataclass
class FakeEmailProvider(EmailProvider):
    sent: list[EmailMessageData] = field(default_factory=list)

    def send(self, message: EmailMessageData) -> bool:
        self.sent.append(message)
        return True


class SMTPEmailProvider(EmailProvider):
    def send(self, message: EmailMessageData) -> bool:
        settings = get_settings()
        if not settings.smtp_host or not settings.smtp_from_email:
            raise EmailConfigurationError("SMTP_HOST and SMTP_FROM_EMAIL are required for SMTP delivery")
        email = EmailMessage()
        email["From"] = f"{settings.smtp_from_name} <{settings.smtp_from_email}>"
        email["To"] = message.recipient
        email["Subject"] = message.subject
        email.set_content(message.body)
        if message.html_body:
            email.add_alternative(message.html_body, subtype="html")
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as client:
            client.starttls()
            if settings.smtp_username:
                client.login(settings.smtp_username, settings.smtp_password)
            client.send_message(email)
        return True