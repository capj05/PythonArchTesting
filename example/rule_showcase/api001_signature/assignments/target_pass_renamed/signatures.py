"""target_pass_renamed -- renames the parameter on rename_allowed only.

``rename_allowed`` is declared with ``allow_param_rename=True`` so the
positional rename ``value -> magnitude`` is accepted. ``rename_forbidden``
keeps the original name.
"""


def compatible_baseline(a: int, b: str) -> bool:
    return bool(a) and bool(b)


def flexible_extras(name: str) -> None:
    del name


def exact_strict(x: int, y: int) -> int:
    return x + y


def rename_allowed(magnitude: int) -> int:
    return magnitude * 2


def rename_forbidden(value: int) -> int:
    return value * 2


def must_keep_return(query: str) -> dict[str, str]:
    return {"query": query}


def return_ignore(query: str) -> dict[str, str]:
    return {"query": query}
