"""target_fail_wrong_signature -- ``compute`` drops a required parameter
and changes its return annotation. Even under signature_mode="compatible"
this is incompatible (missing ``y``), so it must FAIL.
"""


class Service:
    def process(self, payload: dict) -> bool:
        return bool(payload)

    def validate(self, value: str) -> bool:
        return bool(value)

    def compute(self, x: int) -> str:
        # missing parameter `y`, wrong return type.
        return str(x)

    def count_items(self) -> int:
        return 0

    def helper(self) -> None:
        return None

    def internal_check(self) -> None:
        return None

    def optional_hook(self) -> None:
        return None
