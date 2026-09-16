"""target_pass_return_ignore_drift -- drift on return_annotation='ignore' is OK."""


def compatible_baseline(a: int, b: str) -> bool:
    return bool(a) and bool(b)


def flexible_extras(name: str) -> None:
    del name


def exact_strict(x: int, y: int) -> int:
    return x + y


def rename_allowed(value: int) -> int:
    return value * 2


def rename_forbidden(value: int) -> int:
    return value * 2


def must_keep_return(query: str) -> dict[str, str]:
    return {"query": query}


def return_ignore(query: str) -> list[str]:
    """Return type drifted from ``dict[str, str]`` to ``list[str]``;
    the rule should still pass because ``return_annotation='ignore'``.
    """
    return [query]
