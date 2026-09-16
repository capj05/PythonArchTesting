"""target_fail_missing_param -- drops parameter ``b`` from compatible_baseline."""


def compatible_baseline(a: int) -> bool:
    """Missing parameter ``b: str`` -- compatible mode still requires it."""
    return bool(a)


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


def return_ignore(query: str) -> dict[str, str]:
    return {"query": query}
