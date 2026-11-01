"""Discount strategies."""

from __future__ import annotations


class NoDiscount:

    def apply(self, total: float) -> float:
        raise NotImplementedError


class PercentDiscount:

    def __init__(self, percent: float) -> None:
        raise NotImplementedError

    def apply(self, total: float) -> float:
        raise NotImplementedError
