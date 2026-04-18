from pythonarchtesting.config.data import create_config_from_dict
from pythonarchtesting.report.api import (
    compute_aggregate_exit_code,
    compute_target_exit_code as compute_exit_code,
)


class _DummyConfig:
    def __init__(self, warnings_as_fail: bool) -> None:
        self._warnings_as_fail = warnings_as_fail

    def getboolean(self, section: str, key: str, default=None):
        if section == "report" and key == "warnings_as_fail":
            return self._warnings_as_fail
        return default


def test_compute_exit_code_warnings_as_fail():
    results = [
        {"status": "WARNING", "severity": "warning"},
        {"status": "SKIPPED", "severity": "warning"},
    ]
    assert compute_exit_code(results, _DummyConfig(False)) == 0
    assert compute_exit_code(results, _DummyConfig(True)) == 1


class _ExitState:
    def __init__(self, exit_code: int) -> None:
        self.exit_code = exit_code


def test_compute_aggregate_exit_code_policies():
    targets = [_ExitState(1), _ExitState(0)]

    cfg = create_config_from_dict({"report": {"multi_target_exit_policy": "any_fail"}})
    assert compute_aggregate_exit_code(targets, cfg) == 1

    cfg = create_config_from_dict({"report": {"multi_target_exit_policy": "all_fail"}})
    assert compute_aggregate_exit_code(targets, cfg) == 0
    assert compute_aggregate_exit_code([_ExitState(1), _ExitState(1)], cfg) == 1

    cfg = create_config_from_dict(
        {"report": {"multi_target_exit_policy": "threshold", "fail_threshold": 2}}
    )
    assert compute_aggregate_exit_code(targets, cfg) == 0
    assert compute_aggregate_exit_code([_ExitState(1), _ExitState(1)], cfg) == 1
