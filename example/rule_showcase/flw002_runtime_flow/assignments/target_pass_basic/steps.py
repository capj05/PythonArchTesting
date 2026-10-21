"""Processing steps of the import pipeline, one function per step."""

from __future__ import annotations

from typing import Any


def parse(line: str) -> dict[str, Any]:
    name, _, age = line.partition(";")
    return {"name": name.strip(), "age": age.strip()}


def validate(record: dict[str, Any]) -> dict[str, Any]:
    if not record["name"] or not record["age"].isdigit():
        raise ValueError(f"invalid record: {record}")
    return {**record, "age": int(record["age"])}


def enrich(record: dict[str, Any]) -> dict[str, Any]:
    return {**record, "adult": record["age"] >= 18}


def store(record: dict[str, Any], sink: list[dict[str, Any]]) -> None:
    sink.append(record)
