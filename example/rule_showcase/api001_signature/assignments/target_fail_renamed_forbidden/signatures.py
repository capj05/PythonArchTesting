"""target_fail_renamed_forbidden -- renames ``value`` on rename_forbidden."""


def compatible_baseline(a: int, b: str) -> bool:
    return bool(a) and bool(b)


def flexible_extras(name: str) -> None:
    del name


def exact_strict(x: int, y: int) -> int:
    return x + y


def rename_allowed(value: int) -> int:
    return value * 2


def rename_forbidden(magnitude: int) -> int:
    """Renamed positional parameter on a rule with ``allow_param_rename=False``."""
    return magnitude * 2


def must_keep_return(query: str) -> dict[str, str]:
    return {"query": query}


def return_ignore(query: str) -> dict[str, str]:
    return {"query": query}
