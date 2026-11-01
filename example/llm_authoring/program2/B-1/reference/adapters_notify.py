"""Driven adapter: a notifier that keeps the messages in an outbox."""

from __future__ import annotations

from typing import Annotated

from pythonarchtesting.rules import implements_protocol, implements_runtime_protocol

from .ports import Notifier


class OutboxNotifier:
    __archtest__: Annotated[
        None,
        implements_protocol(Notifier),
        implements_runtime_protocol(Notifier, cases=[{"args": []}]),
    ]

    def __init__(self) -> None:
        self.sent: list[tuple[str, str]] = []

    def send(self, member: str, text: str) -> None:
        self.sent.append((member, text))
