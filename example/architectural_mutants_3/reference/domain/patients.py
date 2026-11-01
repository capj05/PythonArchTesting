"""Patients of the clinic."""

from __future__ import annotations


class Patient:
    def __init__(self, patient_id: str, name: str, email: str) -> None:
        if not patient_id:
            raise ValueError("a patient needs an id")
        if "@" not in email:
            raise ValueError(f"not an e-mail address: {email!r}")
        self.patient_id = patient_id
        self.name = name
        self.email = email

    def greeting(self) -> str:
        first = self.name.split()[0] if self.name else self.patient_id
        return f"Dear {first}"
