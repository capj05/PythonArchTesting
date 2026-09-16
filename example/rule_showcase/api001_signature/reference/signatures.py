"""Reference functions for the required_entity_signature showcase.

Each function pins a different combination of parameters of
``required_entity_signature`` so that targets can demonstrate the verdict
for one specific concern at a time. The function bodies themselves are
trivial -- only the *signature* is checked.
"""

from typing import Annotated

from pythonarchtesting.rules import required_entity_signature


def compatible_baseline(
    a: int,
    b: str,
) -> Annotated[
    bool,
    required_entity_signature(),  # default: mode="compatible"
]:
    """Default-mode baseline: target must keep the same parameter shape."""
    return bool(a) and bool(b)


def flexible_extras(
    name: str,
) -> Annotated[
    None,
    required_entity_signature(mode="compatible", allow_extra_params=True),
]:
    """Target may add extra parameters with defaults under compatible mode."""
    del name


def exact_strict(
    x: int,
    y: int,
) -> Annotated[
    int,
    required_entity_signature(mode="exact", allow_extra_params=False),
]:
    """Exact mode: extra params, renames, and reorders are all forbidden."""
    return x + y


def rename_allowed(
    value: int,
) -> Annotated[
    int,
    required_entity_signature(mode="compatible", allow_param_rename=True),
]:
    """Parameter renames are explicitly tolerated."""
    return value * 2


def rename_forbidden(
    value: int,
) -> Annotated[
    int,
    required_entity_signature(mode="compatible", allow_param_rename=False),
]:
    """Parameter renames are explicitly rejected."""
    return value * 2


def must_keep_return(
    query: str,
) -> Annotated[
    dict[str, str],
    required_entity_signature(return_annotation="error"),
]:
    """Return-annotation drift is escalated to a hard error."""
    return {"query": query}


def return_ignore(
    query: str,
) -> Annotated[
    dict[str, str],
    required_entity_signature(return_annotation="ignore"),
]:
    """Return-annotation drift is silently tolerated."""
    return {"query": query}
