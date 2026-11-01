"""A notifier that keeps the e-mails it would send (an outbox)."""

from __future__ import annotations


class OutboxNotifier:

    def __init__(self) -> None:
        raise NotImplementedError

    def send(self, address: str, subject: str, body: str) -> None:
        raise NotImplementedError
