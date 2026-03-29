from __future__ import annotations

import sys
import time


def test_rules_lazy_surface_only_exposes_supported_core_markers() -> None:
    modules_to_clear = [name for name in sys.modules if name.startswith("src.rules")]
    for name in modules_to_clear:
        del sys.modules[name]

    import src.rules

    assert hasattr(src.rules, "required_entity_signature")
    assert hasattr(src.rules, "required_method")
    assert not hasattr(src.rules, "list_comprehension")
    assert not hasattr(src.rules, "detect_singleton")

    assert src.rules.required_entity_signature._cached is None

    marker = src.rules.required_entity_signature(mode="compatible")

    assert marker.__class__.__name__ == "RuleMarker"
    assert marker.kind == "required_entity_signature"
    assert marker.params["mode"] == "compatible"
    assert src.rules.required_entity_signature._cached is not None


def test_rules_module_import_performance() -> None:
    modules_to_clear = [name for name in sys.modules if name.startswith("src.rules")]
    for name in modules_to_clear:
        del sys.modules[name]

    start = time.time()
    import src.rules  # noqa: F401

    assert time.time() - start < 0.1
