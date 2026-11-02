"""Driven adapter: a notifier that keeps the messages in an outbox."""

from __future__ import annotations


class OutboxNotifier:

    def __init__(self) -> None:
        raise NotImplementedError

    def send(self, member: str, text: str) -> None:
        raise NotImplementedError
