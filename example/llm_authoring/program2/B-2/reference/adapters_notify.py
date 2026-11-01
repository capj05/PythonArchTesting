"""Driven adapter: a notifier that keeps the messages in an outbox."""

from __future__ import annotations

from typing import Annotated

from pythonarchtesting.rules import implements_protocol


class OutboxNotifier:
    __archtest__: Annotated[None, implements_protocol("ports.Notifier")]

    def __init__(self) -> None:
        self.sent: list[tuple[str, str]] = []

    def send(self, member: str, text: str) -> None:
        self.sent.append((member, text))
