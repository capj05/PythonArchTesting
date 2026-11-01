"""Composition root: the only module that knows the concrete adapters."""

from __future__ import annotations
from .adapters_memory import FixedClock, InMemoryLoanStore
from .adapters_notify import OutboxNotifier
from .application import LendingService


def build(day: int = 1) -> LendingService:
    raise NotImplementedError
