"""Target: target_fail_member_kind — ``NoConstantsClass`` defines a constant."""


class NoSecret:
    public: str = "ok"


class NoDangerousAliases:
    def safe_eval(self) -> None:
        return None


class NoDebugMethods:
    def run(self) -> None:
        return None


class NoConstantsClass:
    MAX_RETRIES = 3  # forbidden constant (member_kind="constant", regex ^[A-Z_]+$)
    name: str = "x"

    def get_name(self) -> str:
        return self.name


class DeclaredNoSecret:
    public: str = "ok"
