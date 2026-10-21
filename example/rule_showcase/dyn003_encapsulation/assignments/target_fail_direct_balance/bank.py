"""Transfer that edits both balances from outside ``Account``."""

from __future__ import annotations

from .account import Account


def transfer(source: Account, target: Account, amount: float) -> None:
    source.balance -= amount
    target.balance += amount
