"""
Determinism tests for module discovery and reference lookup.
"""

from types import SimpleNamespace

import pytest

from src.config.data import create_config_from_dict
from src.state import ProjectState


@pytest.fixture(autouse=True)
def reset_project_state():
    return ProjectState("/test", [])


def test_discover_modules_sorted(tmp_path):
    (tmp_path / "b.py").write_text("x = 1")
    (tmp_path / "a.py").write_text("x = 2")
    config = create_config_from_dict({"discovery": {"exclude_hidden_dirs": False}})

    state = ProjectState(str(tmp_path), [], config=config)
    state.initialize(str(tmp_path))

    modules = state.discover_modules()
    assert modules == ["a", "b"]


def test_import_order_matches_discovery(tmp_path):
    (tmp_path / "b.py").write_text("x = 1")
    (tmp_path / "a.py").write_text("x = 2")
    config = create_config_from_dict({"discovery": {"exclude_hidden_dirs": False}})

    state = ProjectState(str(tmp_path), [], config=config)
    state.initialize(str(tmp_path))

    modules = state.discover_modules()
    assert state.import_order == modules


def test_find_reference_function_tiebreak_deterministic(tmp_path):
    state = ProjectState(str(tmp_path), [])
    state.initialize(str(tmp_path))

    def make_foo():
        def foo():
            return "value"

        return foo

    ref1 = make_foo()
    ref1.__module__ = "pkg1.mod"
    ref2 = make_foo()
    ref2.__module__ = "pkg2.mod"

    module1 = SimpleNamespace(foo=ref1)
    module2 = SimpleNamespace(foo=ref2)

    state.imported_modules["pkg1.mod"] = module1
    state.imported_modules["pkg2.mod"] = module2
    state.target_functions["pkg1.mod"] = [ref1]
    state.target_functions["pkg2.mod"] = [ref2]
    state.import_order = ["pkg1.mod", "pkg2.mod"]

    target_func = make_foo()
    target_func.__module__ = "pkg2.mod"
    target_func.__qualname__ = "target.foo"

    result = state.find_reference_function(target_func)
    assert result is ref2
