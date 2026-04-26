from typing import Annotated

from pythonarchtesting.rules import does_not_have, require_method_set, required_method


class TestCaseStyle:
    __archtest__: Annotated[
        None,
        require_method_set(name_match="regex", pattern=r"test_.*", min_count=1),
        does_not_have("debug", member_kind="method"),
    ]

    def setUp(self) -> None:
        __archtest__: Annotated[
            None,
            required_method(signature_mode="any", allow_missing=True),
        ]

    def tearDown(self) -> None:
        __archtest__: Annotated[
            None,
            required_method(signature_mode="any", allow_missing=True),
        ]
