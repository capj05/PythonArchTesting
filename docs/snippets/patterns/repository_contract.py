from typing import Annotated

from pythonarchtesting.rules import does_not_have, required_factory, required_method


class RepositoryReference:
    __archtest__: Annotated[
        None,
        does_not_have("commit", member_kind="method"),
    ]

    @classmethod
    def from_config(cls, url: str):
        __archtest__: Annotated[
            None,
            required_factory(
                signature_mode="any",
                name_match="alias",
                aliases=["build", "open"],
            ),
        ]
        return cls()

    def get(self, item_id: str) -> object:
        __archtest__: Annotated[
            None,
            required_method(
                name_match="alias",
                aliases=["load", "fetch"],
            ),
        ]
        return object()
