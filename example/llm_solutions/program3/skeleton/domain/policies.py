"""Cancellation policies: what a patient pays for cancelling late.

A policy is chosen when the application is composed, not by the use case.
"""

from __future__ import annotations
from .schedule import Appointment


class FreeCancellation:

    def fee(self, appointment: Appointment, day: int, hour: int) -> int:
        raise NotImplementedError


class LateCancellationFee:
    """``amount`` when the visit starts within ``hours`` of the cancellation."""

    def __init__(self, hours: int, amount: int) -> None:
        raise NotImplementedError

    def fee(self, appointment: Appointment, day: int, hour: int) -> int:
        raise NotImplementedError


class TieredFee:
    """A list of ``(hours, amount)`` steps: the first step the cancellation is within."""

    def __init__(self, steps: list[tuple[int, int]]) -> None:
        raise NotImplementedError

    def fee(self, appointment: Appointment, day: int, hour: int) -> int:
        raise NotImplementedError
