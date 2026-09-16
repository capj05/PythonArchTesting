"""Reference module for the NEG001 / does_not_have showcase.

One ``does_not_have`` marker per class so each target isolates a single
concern (explicit-name absence, alias set, regex pattern, member-kind
filtering, declared-only enforcement).
"""

from typing import Annotated

from pythonarchtesting.rules import does_not_have


class NoSecret:
    """Must not have a method/attribute named 'secret'."""

    __archtest__: Annotated[None, does_not_have("secret")]

    public: str = "ok"


class NoDangerousAliases:
    """Must not have any of: 'eval_input', 'exec_code', 'shell_out'."""

    __archtest__: Annotated[
        None,
        does_not_have(
            name_match="alias",
            aliases=["eval_input", "exec_code", "shell_out"],
        ),
    ]


class NoDebugMethods:
    """No method matching ^debug_.*$."""

    __archtest__: Annotated[
        None,
        does_not_have(
            name_match="regex",
            pattern=r"^debug_.*$",
            member_kind="method",
        ),
    ]


class NoConstantsClass:
    """Must have no class-level attributes whose name matches ^[A-Z_]+$.

    ``member_kind`` must be one of {any, method, attribute, property};
    ``constant`` is not a recognised kind, so we filter on
    ``member_kind="attribute"`` and rely on the regex to spot the all-caps
    naming convention.
    """

    __archtest__: Annotated[
        None,
        does_not_have(
            name_match="regex",
            pattern=r"^[A-Z_]+$",
            member_kind="attribute",
        ),
    ]


class DeclaredNoSecret:
    """``declared_only=True`` — inherited 'secret' is allowed; only declared 'secret' fails."""

    __archtest__: Annotated[None, does_not_have("secret", declared_only=True)]
