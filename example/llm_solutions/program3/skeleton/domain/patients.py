"""Patients of the clinic."""

from __future__ import annotations


class Patient:

    def __init__(self, patient_id: str, name: str, email: str) -> None:
        raise NotImplementedError

    def greeting(self) -> str:
        raise NotImplementedError
