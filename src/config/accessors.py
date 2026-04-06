"""
Unified configuration access helpers.

These helpers provide a single read path that supports the Config
dataclass and mapping-like raw configuration data.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, is_dataclass
from typing import Any, overload


def _section_name(section: str) -> str:
    """Map config section names to Config dataclass attribute names."""
    if section == "import":
        return "import_config"
    return section


def _from_config_dataclass(config: Any, section: str, key: str) -> tuple[bool, Any]:
    section_obj = getattr(config, _section_name(section), None)
    if section_obj is None:
        return False, None
    if hasattr(section_obj, key):
        return True, getattr(section_obj, key)
    return False, None


def _from_mapping(config: Any, section: str, key: str) -> tuple[bool, Any]:
    if not isinstance(config, Mapping):
        return False, None

    section_obj = config.get(section)
    if isinstance(section_obj, Mapping) and key in section_obj:
        return True, section_obj[key]

    alt_section = _section_name(section)
    if alt_section != section:
        alt_section_obj = config.get(alt_section)
        if isinstance(alt_section_obj, Mapping) and key in alt_section_obj:
            return True, alt_section_obj[key]

    return False, None


def _from_manager(config: Any, section: str, key: str) -> tuple[bool, Any]:
    getter = getattr(config, "get", None)
    if callable(getter):
        sentinel = object()
        value = getter(section, key, sentinel)
        if value is not sentinel:
            return True, value
    return False, None


def _get_value(config: Any, section: str, key: str, default: Any) -> Any:
    found, value = _from_config_dataclass(config, section, key)
    if found:
        return value

    found, value = _from_mapping(config, section, key)
    if found:
        return value

    found, value = _from_manager(config, section, key)
    if found:
        return value

    return default


@overload
def get_bool(config: Any, section: str, key: str, default: bool) -> bool: ...


@overload
def get_bool(config: Any, section: str, key: str, default: None) -> None: ...


def get_bool(config: Any, section: str, key: str, default: bool | None) -> bool | None:
    for method_name in ("get_boolean", "getboolean"):
        method = getattr(config, method_name, None)
        if callable(method):
            try:
                value = method(section, key, default)
                if value is None:
                    return default
                if isinstance(value, bool):
                    return value
                if isinstance(value, str):
                    return value.strip().lower() in {"true", "1", "yes", "on"}
                return bool(value)
            except Exception:
                return default
    value = _get_value(config, section, key, default)
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes", "on"}
    return bool(value)


@overload
def get_int(config: Any, section: str, key: str, default: int) -> int: ...


@overload
def get_int(config: Any, section: str, key: str, default: None) -> None: ...


def get_int(config: Any, section: str, key: str, default: int | None) -> int | None:
    for method_name in ("get_int", "getint"):
        method = getattr(config, method_name, None)
        if callable(method):
            try:
                value = method(section, key, default)
                if value is None:
                    return default
                return int(value)
            except (TypeError, ValueError):
                return default
    value = _get_value(config, section, key, default)
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def get_float(config: Any, section: str, key: str, default: float) -> float:
    for method_name in ("get_float", "getfloat"):
        method = getattr(config, method_name, None)
        if callable(method):
            try:
                value = method(section, key, default)
                return float(value)
            except (TypeError, ValueError):
                return default
    value = _get_value(config, section, key, default)
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def get_str(config: Any, section: str, key: str, default: str) -> str:
    method = getattr(config, "get_str", None)
    if callable(method):
        try:
            value = method(section, key, default)
            if value is None:
                return default
            return str(value)
        except Exception:
            return default
    value = _get_value(config, section, key, default)
    if value is None:
        return default
    return str(value)


def get_list(config: Any, section: str, key: str, default: list[str]) -> list[str]:
    for method_name in ("get_list", "getlist"):
        method = getattr(config, method_name, None)
        if callable(method):
            try:
                value = method(section, key, default)
                if isinstance(value, list):
                    return [str(item) for item in value]
                if isinstance(value, tuple):
                    return [str(item) for item in value]
                if isinstance(value, set):
                    return [str(item) for item in sorted(value)]
                if isinstance(value, str):
                    return [item.strip() for item in value.split(",") if item.strip()]
                return list(default)
            except Exception:
                return list(default)
    value = _get_value(config, section, key, default)
    if isinstance(value, list):
        return [str(item) for item in value]
    if isinstance(value, tuple):
        return [str(item) for item in value]
    if isinstance(value, set):
        return [str(item) for item in sorted(value)]
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    return list(default)


def get_section(config: Any, section: str) -> dict[str, Any]:
    def _raw_section() -> dict[str, Any]:
        raw_cfg = getattr(config, "raw", None)
        if isinstance(raw_cfg, Mapping):
            raw_section = raw_cfg.get(section)
            if isinstance(raw_section, Mapping):
                return dict(raw_section)
            alt_section = raw_cfg.get(_section_name(section))
            if isinstance(alt_section, Mapping):
                return dict(alt_section)
        return {}

    section_obj = getattr(config, _section_name(section), None)
    if section_obj is not None:
        raw = _raw_section()
        if is_dataclass(section_obj) and not isinstance(section_obj, type):
            typed = asdict(section_obj)
            raw.update(typed)
            return raw
        if hasattr(section_obj, "__dict__"):
            typed = dict(vars(section_obj))
            raw.update(typed)
            return raw
        try:
            typed = dict(section_obj)
            raw.update(typed)
            return raw
        except Exception:
            return raw

    if isinstance(config, Mapping):
        raw_value = config.get(section)
        if isinstance(raw_value, Mapping):
            return dict(raw_value)
        alt_value = config.get(_section_name(section))
        if isinstance(alt_value, Mapping):
            return dict(alt_value)
        return {}

    get_section_fn = getattr(config, "get_section", None)
    if callable(get_section_fn):
        raw_value = get_section_fn(section)
        if isinstance(raw_value, Mapping):
            return dict(raw_value)

    get_all_fn = getattr(config, "get_all", None)
    if callable(get_all_fn):
        raw_all = get_all_fn()
        if isinstance(raw_all, Mapping):
            raw_value = raw_all.get(section)
            if isinstance(raw_value, Mapping):
                return dict(raw_value)

    return {}


__all__ = [
    "get_bool",
    "get_int",
    "get_float",
    "get_str",
    "get_list",
    "get_section",
]
