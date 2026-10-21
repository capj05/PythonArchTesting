"""Transfer through the accounts' own methods, as the reference does."""

from __future__ import annotations

from .account import Account


def transfer(source: Account, target: Account, amount: float) -> None:
    source.withdraw(amount)
    target.deposit(amount)
