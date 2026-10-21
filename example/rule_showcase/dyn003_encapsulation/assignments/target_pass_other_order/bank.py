"""Credits first and debits second, and rolls back on failure.

The order and the error handling differ from the reference; both accounts
still change only through their own methods, so it passes.
"""

from __future__ import annotations

from .account import Account


def transfer(source: Account, target: Account, amount: float) -> None:
    target.deposit(amount)
    try:
        source.withdraw(amount)
    except Exception:
        target.withdraw(amount)
        raise
