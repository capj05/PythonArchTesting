"""The same steps, computing different things: values are never compared."""

from __future__ import annotations

from typing import Any


def parse(line: str) -> dict[str, Any]:
    fields = [part.strip() for part in line.split(";")]
    return {"name": fields[0].title(), "age": fields[1] if len(fields) > 1 else ""}


def validate(record: dict[str, Any]) -> dict[str, Any]:
    if not record["age"].isdigit():
        raise ValueError("age must be a number")
    record["age"] = int(record["age"])
    return record


def enrich(record: dict[str, Any]) -> dict[str, Any]:
    record["category"] = "senior" if record["age"] >= 65 else "regular"
    return record


def store(record: dict[str, Any], sink: list[dict[str, Any]]) -> None:
    sink.insert(0, dict(record))
