"""target_pass_extras_compatible -- adds defaulted extra params on flexible_extras."""


def compatible_baseline(a: int, b: str) -> bool:
    return bool(a) and bool(b)


def flexible_extras(name: str, *, debug: bool = False, retries: int = 0) -> None:
    """Two extra keyword-only params with defaults; tolerated under
    ``mode='compatible', allow_extra_params=True``.
    """
    del name, debug, retries


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
