"""A notifier that keeps the e-mails it would send (an outbox)."""

from __future__ import annotations

from typing import Annotated

from pythonarchtesting.rules import implements_protocol, implements_runtime_protocol

from ..ports.notifier import Notifier


class OutboxNotifier:
    __archtest__: Annotated[
        None,
        implements_protocol(Notifier),
        implements_runtime_protocol(Notifier, cases=[{"args": []}]),
    ]

    def __init__(self) -> None:
        self.sent: list[tuple[str, str, str]] = []

    def send(self, address: str, subject: str, body: str) -> None:
        self.sent.append((address, subject, body))
