"""A notifier that keeps the e-mails it would send (an outbox)."""

from __future__ import annotations


class OutboxNotifier:
    def __init__(self) -> None:
        self.sent: list[tuple[str, str, str]] = []

    def send(self, address: str, subject: str, body: str) -> None:
        self.sent.append((address, subject, body))
