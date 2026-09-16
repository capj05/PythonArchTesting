"""Target: target_fail_explicit_name — ``NoSecret`` defines a forbidden ``secret`` attribute."""


class NoSecret:
    public: str = "ok"
    secret: str = "leaked"  # violates does_not_have("secret")


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


class DeclaredNoSecret:
    public: str = "ok"
