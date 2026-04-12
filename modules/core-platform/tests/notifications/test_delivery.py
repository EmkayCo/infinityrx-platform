"""Delivery backend smoke tests."""

from __future__ import annotations

from src.notifications.delivery import (
    EmailMessage,
    NoOpEmailDelivery,
    NoOpSmsDelivery,
    SmtpEmailDelivery,
)


def test_noop_email_records_sent():
    d = NoOpEmailDelivery()
    msg = EmailMessage(to="u@example.com", subject="s", body="b")
    d.send(msg)
    assert d.sent == [msg]


def test_noop_sms_records_sent():
    d = NoOpSmsDelivery()
    d.send("user-1", "hello")
    assert d.sent == [("user-1", "hello")]


def test_smtp_email_delivery_holds_config():
    d = SmtpEmailDelivery(
        host="smtp.local",
        port=25,
        username="user",
        password="pass",
        sender="from@local",
        use_tls=True,
    )
    assert d._host == "smtp.local"
    assert d._port == 25
    assert d._use_tls is True
