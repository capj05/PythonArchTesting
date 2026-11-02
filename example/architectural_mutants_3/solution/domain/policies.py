"""Cancellation policies: what a patient pays for cancelling late.

A policy is chosen when the application is composed, not by the use case.
"""

from __future__ import annotations

from .schedule import Appointment


class FreeCancellation:
    def fee(self, appointment: Appointment, day: int, hour: int) -> int:
        return 0


class LateCancellationFee:
    """``amount`` when the visit starts within ``hours`` of the cancellation."""

    def __init__(self, hours: int, amount: int) -> None:
        if hours < 0 or amount < 0:
            raise ValueError("hours and amount must not be negative")
        self.hours = hours
        self.amount = amount

    def fee(self, appointment: Appointment, day: int, hour: int) -> int:
        left = appointment.slot.hours_from(day, hour)
        return self.amount if left < self.hours else 0


class TieredFee:
    """A list of ``(hours, amount)`` steps: the first step the cancellation is within."""

    def __init__(self, steps: list[tuple[int, int]]) -> None:
        self.steps = sorted(steps)

    def fee(self, appointment: Appointment, day: int, hour: int) -> int:
        left = appointment.slot.hours_from(day, hour)
        for hours, amount in self.steps:
            if left < hours:
                return amount
        return 0
