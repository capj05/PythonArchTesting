"""Reference transfer for the DYN003 ``forbid_foreign_writes`` showcase.

``transfer`` may change account balances only by asking the accounts to change
themselves (``withdraw``, ``deposit``). Assigning ``account.balance`` from
here would move the account's invariant (no overdraft) out of the class that
owns it. Python has no private attributes, so the rule watches assignments
while the code runs: an attribute of a target class may be set only by that
class's own methods.

The case only gives arguments; the resulting balances are not checked.
"""

from __future__ import annotations

from typing import Annotated

from pythonarchtesting.rules import forbid_foreign_writes

from .account import Account


def transfer(source: Account, target: Account, amount: float) -> None:
    __archtest__: Annotated[  # noqa: F842
        None,
        forbid_foreign_writes(
            cases=[
                {
                    "args": [
                        {"$new": "account.Account", "args": ["ada", 100.0]},
                        {"$new": "account.Account", "args": ["bob", 20.0]},
                        30.0,
                    ]
                }
            ],
        ),
    ]
    source.withdraw(amount)
    target.deposit(amount)
