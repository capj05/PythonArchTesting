"""The current time, as the clinic counts it: a day and an hour."""

from __future__ import annotations
from typing import Protocol


class Clock(Protocol):

    def now(self) -> tuple[int, int]: ...
