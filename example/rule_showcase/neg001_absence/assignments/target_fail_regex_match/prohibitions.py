"""Target: target_fail_regex_match — ``NoDebugMethods`` defines ``debug_dump``."""


class NoSecret:
    public: str = "ok"


class NoDangerousAliases:
    def safe_eval(self) -> None:
        return None


class NoDebugMethods:
    def run(self) -> None:
        return None

    def debug_dump(self) -> None:  # matches forbidden pattern ^debug_.*$
        return None


class NoConstantsClass:
    name: str = "x"

    def get_name(self) -> str:
        return self.name


class DeclaredNoSecret:
    public: str = "ok"
