"""How patients are told about their appointments."""

from __future__ import annotations

from typing import Protocol


class Notifier(Protocol):
    def send(self, address: str, subject: str, body: str) -> None: ...
