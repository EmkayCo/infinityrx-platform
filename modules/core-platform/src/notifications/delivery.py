"""Delivery backends: in-app (row), email (SMTP), SMS (stubbed)."""

from __future__ import annotations

import logging
import smtplib
from dataclasses import dataclass
from email.mime.text import MIMEText
from typing import Protocol

_logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class EmailMessage:
    to: str
    subject: str
    body: str


class EmailDelivery(Protocol):
    def send(self, message: EmailMessage) -> None: ...


class SmsDelivery(Protocol):  # pragma: no cover - interface only
    def send(self, to: str, message: str) -> None: ...


class NoOpEmailDelivery:
    """In-process fake used in tests and local dev without SMTP."""

    def __init__(self) -> None:
        self.sent: list[EmailMessage] = []

    def send(self, message: EmailMessage) -> None:
        self.sent.append(message)


class SmtpEmailDelivery:
    """Stdlib ``smtplib`` backed email sender.

    Kept intentionally thin — the audit trail of what was sent lives in
    the notifications table itself, not here.
    """

    def __init__(
        self,
        *,
        host: str,
        port: int,
        username: str | None = None,
        password: str | None = None,
        sender: str = "noreply@infinityrx.local",
        use_tls: bool = False,
    ) -> None:
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._sender = sender
        self._use_tls = use_tls

    def send(self, message: EmailMessage) -> None:  # pragma: no cover - network
        msg = MIMEText(message.body)
        msg["Subject"] = message.subject
        msg["From"] = self._sender
        msg["To"] = message.to
        with smtplib.SMTP(self._host, self._port) as smtp:
            if self._use_tls:
                smtp.starttls()
            if self._username and self._password:
                smtp.login(self._username, self._password)
            smtp.sendmail(self._sender, [message.to], msg.as_string())


class NoOpSmsDelivery:
    """Placeholder SMS delivery.

    Real Twilio/SNS wiring is tracked in
    ``modules/core-platform/tasks/todo.md`` — see task
    ``notifications.sms.wire-provider``.
    """

    def __init__(self) -> None:
        self.sent: list[tuple[str, str]] = []

    def send(self, to: str, message: str) -> None:
        self.sent.append((to, message))
