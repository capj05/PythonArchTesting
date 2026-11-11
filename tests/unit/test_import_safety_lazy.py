from __future__ import annotations

import sys
import time


def test_rules_lazy_surface_only_exposes_supported_core_markers() -> None:
    modules_to_clear = [
        name for name in sys.modules if name.startswith("pythonarchtesting.rules")
    ]
    for name in modules_to_clear:
        del sys.modules[name]

    import pythonarchtesting.rules

    assert hasattr(pythonarchtesting.rules, "required_entity_signature")
    assert hasattr(pythonarchtesting.rules, "required_method")
    assert not hasattr(pythonarchtesting.rules, "list_comprehension")
    assert not hasattr(pythonarchtesting.rules, "detect_singleton")

    assert pythonarchtesting.rules.required_entity_signature._cached is None

    marker = pythonarchtesting.rules.required_entity_signature(mode="compatible")

    assert marker.__class__.__name__ == "RuleMarker"
    assert marker.kind == "required_entity_signature"
    assert marker.params["mode"] == "compatible"
    assert pythonarchtesting.rules.required_entity_signature._cached is not None


def test_rules_module_import_performance() -> None:
    modules_to_clear = [
        name for name in sys.modules if name.startswith("pythonarchtesting.rules")
    ]
    for name in modules_to_clear:
        del sys.modules[name]

    start = time.time()
    import pythonarchtesting.rules  # noqa: F401

    assert time.time() - start < 0.1


def test_flow_cfg_imports_on_its_own() -> None:
    """flow_cfg -> rules.compilation -> evaluators -> variable_flow -> flow_cfg
    is a cycle; it must not break when flow_cfg is the first module imported."""
    import subprocess

    result = subprocess.run(  # nosec B603
        [sys.executable, "-c", "import pythonarchtesting.execution.flow_cfg"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
