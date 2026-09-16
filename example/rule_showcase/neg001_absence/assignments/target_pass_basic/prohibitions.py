"""Target: target_pass_basic — verbatim compliant copy of all five reference classes."""


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


class DeclaredNoSecret:
    public: str = "ok"
