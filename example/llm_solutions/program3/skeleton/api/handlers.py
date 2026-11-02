"""Request handlers: they talk to the booking service only."""

from __future__ import annotations
from typing import Any
from ..application.booking import BookingError, BookingService, summary
from ..application.reminders import ReminderService
from .serializers import RequestError, as_int, error, ok, require


def book(request: dict[str, Any], service: BookingService) -> dict[str, Any]:
    raise NotImplementedError


def cancel(request: dict[str, Any], service: BookingService) -> dict[str, Any]:
    raise NotImplementedError


def move(request: dict[str, Any], service: BookingService) -> dict[str, Any]:
    raise NotImplementedError


def free(request: dict[str, Any], service: BookingService) -> dict[str, Any]:
    raise NotImplementedError


def remind(request: dict[str, Any], reminders: ReminderService) -> dict[str, Any]:
    raise NotImplementedError
