"""The write hides in a module-level helper.

``_move`` is not a method of ``Account``, so its assignment is foreign even
though ``transfer`` itself never touches an attribute.
"""

from __future__ import annotations

from .account import Account


def _move(account: Account, delta: float) -> None:
    account.balance = account.balance + delta


def transfer(source: Account, target: Account, amount: float) -> None:
    source.withdraw(amount)
    _move(target, amount)
