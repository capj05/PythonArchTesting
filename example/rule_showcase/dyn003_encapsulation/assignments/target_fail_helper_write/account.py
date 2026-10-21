"""Account model: the balance is changed only through its own methods."""

from __future__ import annotations


class InsufficientFunds(Exception):
    pass


class Account:
    def __init__(self, owner: str, balance: float = 0.0) -> None:
        self.owner = owner
        self.balance = balance

    def deposit(self, amount: float) -> None:
        self.balance += amount

    def withdraw(self, amount: float) -> None:
        if amount > self.balance:
            raise InsufficientFunds(self.owner)
        self.balance -= amount
