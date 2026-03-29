from pathlib import Path

import pytest

from src.config.projects import resolve_projects_config
from src.exceptions import ConfigurationError


class StubConfig:
    def __init__(self, values=None, lists=None):
        self._values = values or {}
        self._lists = lists or {}
        self.projects = type(
            "Projects",
            (),
            {
                "source_path": ".",
                "targets": [],
                "exclude_patterns": [],
                "project_pattern": "*",
            },
        )()

    def get(self, section, key, default=None):
        return self._values.get((section, key), default)

    def getlist(self, section, key, default=None):
        return self._lists.get((section, key), default or [])


def test_targets_dir_discovery_filters_and_py_check(tmp_path: Path) -> None:
    targets_dir = tmp_path / "targets"
    targets_dir.mkdir()

    project_a = targets_dir / "a"
    project_a.mkdir()
    (project_a / "a.py").write_text("print('a')", encoding="utf-8")

    project_b = targets_dir / "b"
    project_b.mkdir()
    (project_b / "b.txt").write_text("no python", encoding="utf-8")

    project_c = targets_dir / "c"
    project_c.mkdir()
    (project_c / "c.py").write_text("print('c')", encoding="utf-8")

    project_skip = targets_dir / "skipme"
    project_skip.mkdir()
    (project_skip / "s.py").write_text("print('skip')", encoding="utf-8")

    cfg = StubConfig()
    projects = resolve_projects_config(
        cfg,
        targets_dir=str(targets_dir),
        project_pattern="*",
        exclude_patterns=["skipme"],
        env_target_path=None,
    )

    target_ids = [spec.target_id for spec in projects.targets]
    assert target_ids == ["a", "c"]


def test_targets_dir_discovery_allows_nested_python(tmp_path: Path) -> None:
    targets_dir = tmp_path / "targets"
    targets_dir.mkdir()

    project_nested = targets_dir / "nested"
    project_nested.mkdir()
    subpkg = project_nested / "pkg"
    subpkg.mkdir()
    (subpkg / "mod.py").write_text("print('nested')", encoding="utf-8")

    cfg = StubConfig()
    projects = resolve_projects_config(
        cfg,
        targets_dir=str(targets_dir),
        project_pattern="*",
        exclude_patterns=[],
        env_target_path=None,
    )

    target_ids = [spec.target_id for spec in projects.targets]
    assert target_ids == ["nested"]


def test_targets_dir_single_project_root_not_split_into_subpackages(
    tmp_path: Path,
) -> None:
    target_root = tmp_path / "target_ok"
    target_root.mkdir()
    (target_root / "__init__.py").write_text("", encoding="utf-8")
    (target_root / "calculator.py").write_text(
        "def add(a, b): return a + b", encoding="utf-8"
    )

    app_dir = target_root / "app"
    app_dir.mkdir()
    (app_dir / "__init__.py").write_text("", encoding="utf-8")
    (app_dir / "core.py").write_text("VALUE = 1", encoding="utf-8")

    domain_dir = target_root / "domain"
    domain_dir.mkdir()
    (domain_dir / "__init__.py").write_text("", encoding="utf-8")
    (domain_dir / "model.py").write_text("class Model: ...", encoding="utf-8")

    cfg = StubConfig()
    projects = resolve_projects_config(
        cfg,
        targets_dir=str(target_root),
        project_pattern="*",
        exclude_patterns=[],
        env_target_path=None,
    )

    assert len(projects.targets) == 1
    assert projects.targets[0].target_id == "target_ok"
    assert projects.targets[0].path == target_root.resolve()


def test_targets_dir_order_is_deterministic(tmp_path: Path) -> None:
    targets_dir = tmp_path / "targets"
    targets_dir.mkdir()

    for name in ["zeta", "alpha", "beta"]:
        project = targets_dir / name
        project.mkdir()
        (project / "main.py").write_text("# test", encoding="utf-8")

    cfg = StubConfig()
    projects = resolve_projects_config(
        cfg,
        targets_dir=str(targets_dir),
        project_pattern="*",
        exclude_patterns=[],
        env_target_path=None,
    )

    target_ids = [spec.target_id for spec in projects.targets]
    assert target_ids == ["alpha", "beta", "zeta"]


def test_explicit_targets_override_targets_dir(tmp_path: Path) -> None:
    targets_dir = tmp_path / "targets"
    targets_dir.mkdir()

    project_a = targets_dir / "a"
    project_a.mkdir()
    (project_a / "a.py").write_text("print('a')", encoding="utf-8")

    explicit = tmp_path / "explicit"
    explicit.mkdir()
    (explicit / "e.py").write_text("print('e')", encoding="utf-8")

    cfg = StubConfig()
    projects = resolve_projects_config(
        cfg,
        targets=[str(explicit)],
        targets_dir=str(targets_dir),
        project_pattern="*",
        exclude_patterns=[],
        env_target_path=None,
    )

    assert len(projects.targets) == 1
    assert projects.targets[0].path == explicit.resolve()


def test_empty_targets_dir_raises(tmp_path: Path) -> None:
    targets_dir = tmp_path / "targets"
    targets_dir.mkdir()

    cfg = StubConfig()
    with pytest.raises(ConfigurationError):
        resolve_projects_config(
            cfg,
            targets_dir=str(targets_dir),
            project_pattern="*",
            exclude_patterns=[],
            env_target_path=None,
        )


def test_target_ids_deterministic_with_duplicate_names(tmp_path: Path) -> None:
    root_a = tmp_path / "one" / "app"
    root_b = tmp_path / "two" / "app"
    root_a.mkdir(parents=True)
    root_b.mkdir(parents=True)
    (root_a / "main.py").write_text("# a", encoding="utf-8")
    (root_b / "main.py").write_text("# b", encoding="utf-8")

    cfg = StubConfig()
    projects_first = resolve_projects_config(
        cfg,
        targets=[str(root_a), str(root_b)],
        project_pattern="*",
        exclude_patterns=[],
        env_target_path=None,
    )
    projects_second = resolve_projects_config(
        cfg,
        targets=[str(root_b), str(root_a)],
        project_pattern="*",
        exclude_patterns=[],
        env_target_path=None,
    )

    mapping_first = {spec.path: spec.target_id for spec in projects_first.targets}
    mapping_second = {spec.path: spec.target_id for spec in projects_second.targets}
    assert mapping_first == mapping_second
    assert sorted(mapping_first.values()) == ["app", "app-2"]


def test_projects_config_normalizes_source_and_targets(
    tmp_path: Path, monkeypatch
) -> None:
    source = tmp_path / "source"
    target = tmp_path / "targets" / "alpha"
    source.mkdir()
    target.mkdir(parents=True)
    (target / "main.py").write_text("# test", encoding="utf-8")

    monkeypatch.chdir(tmp_path)
    cfg = StubConfig()
    projects = resolve_projects_config(
        cfg,
        source_path="source",
        targets=["targets/alpha"],
        project_pattern="*",
        exclude_patterns=[],
        env_target_path=None,
    )

    assert projects.source_path == source.resolve()
    assert projects.targets[0].path == target.resolve()
