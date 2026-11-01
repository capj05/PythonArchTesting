"""Clocks: a fixed one for tests and demos, and the computer's."""

from __future__ import annotations

import datetime


class FixedClock:
    def __init__(self, day: int, hour: int) -> None:
        self._day = day
        self._hour = hour

    def now(self) -> tuple[int, int]:
        return (self._day, self._hour)


class SystemClock:
    """Days counted from ``start`` (day 1), hours of the local time."""

    def __init__(self, start: datetime.date) -> None:
        self._start = start

    def now(self) -> tuple[int, int]:
        moment = datetime.datetime.now()
        return ((moment.date() - self._start).days + 1, moment.hour)
