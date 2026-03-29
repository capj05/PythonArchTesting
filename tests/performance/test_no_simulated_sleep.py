from __future__ import annotations

from pathlib import Path

import pytest


@pytest.mark.performance
def test_performance_suite_avoids_time_sleep_simulation():
    perf_dir = Path(__file__).resolve().parent
    offenders: list[str] = []

    for file_path in perf_dir.glob("test_*.py"):
        content = file_path.read_text(encoding="utf-8")
        sanitized = content.replace('"time.sleep("', "")
        if "time.sleep(" in sanitized:
            offenders.append(str(file_path))

    assert not offenders, f"Found simulated sleep in performance tests: {offenders}"
