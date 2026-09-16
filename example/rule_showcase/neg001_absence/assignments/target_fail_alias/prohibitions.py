"""Target: target_fail_alias — ``NoDangerousAliases`` defines ``exec_code``."""


class NoSecret:
    public: str = "ok"


class NoDangerousAliases:
    def exec_code(self, code: str) -> None:  # alias 'exec_code' is forbidden
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
