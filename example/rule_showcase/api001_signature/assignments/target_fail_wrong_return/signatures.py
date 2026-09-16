"""target_fail_wrong_return -- changes return type on must_keep_return."""


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


def must_keep_return(query: str) -> list[str]:
    """Return type changed from ``dict[str, str]`` to ``list[str]``;
    ``return_annotation='error'`` should reject this.
    """
    return [query]


def return_ignore(query: str) -> dict[str, str]:
    return {"query": query}
