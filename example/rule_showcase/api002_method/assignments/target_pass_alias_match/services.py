"""target_pass_alias_match -- ``validate`` is renamed to ``check``,
which is one of the configured aliases on the reference rule.
"""


class Service:
    def process(self, payload: dict) -> bool:
        return bool(payload)

    def check(self, value: str) -> bool:
        # alias of `validate` -- accepted because name_match="alias".
        return bool(value)

    def compute(self, x: int, y: int) -> int:
        return x + y

    def count_items(self) -> int:
        return 0

    def helper(self) -> None:
        return None

    def internal_check(self) -> None:
        return None

    def optional_hook(self) -> None:
        return None
