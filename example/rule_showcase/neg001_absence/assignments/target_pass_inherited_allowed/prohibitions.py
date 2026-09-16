"""Target: target_pass_inherited_allowed.

``DeclaredNoSecret`` inherits ``secret`` from ``_Base``. With
``declared_only=True`` on the rule, the inherited member is allowed because
only declared members are inspected.
"""


class NoSecret:
    public: str = "ok"


class NoDangerousAliases:
    def safe_eval(self) -> None:
        return None


class NoDebugMethods:
    def run(self) -> None:
        return None


class NoConstantsClass:
    name: str = "x"

    def get_name(self) -> str:
        return self.name


class _Base:
    secret: str = "inherited"


class DeclaredNoSecret(_Base):
    public: str = "ok"
