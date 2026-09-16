"""target_fail_missing_method -- ``process`` is omitted entirely.

The default ``required_method()`` rule on ``process`` has
``allow_missing=False``, so this must FAIL.
"""


class Service:
    # process(...) intentionally missing.

    def validate(self, value: str) -> bool:
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
