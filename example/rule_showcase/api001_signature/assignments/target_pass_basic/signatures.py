"""target_pass_basic -- mirrors every reference signature verbatim."""


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


def return_ignore(query: str) -> dict[str, str]:
    return {"query": query}
