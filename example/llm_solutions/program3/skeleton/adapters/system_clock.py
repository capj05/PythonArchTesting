"""Clocks: a fixed one for tests and demos, and the computer's."""

from __future__ import annotations
import datetime


class FixedClock:

    def __init__(self, day: int, hour: int) -> None:
        raise NotImplementedError

    def now(self) -> tuple[int, int]:
        raise NotImplementedError


class SystemClock:
    """Days counted from ``start`` (day 1), hours of the local time."""

    def __init__(self, start: datetime.date) -> None:
        raise NotImplementedError

    def now(self) -> tuple[int, int]:
        raise NotImplementedError
