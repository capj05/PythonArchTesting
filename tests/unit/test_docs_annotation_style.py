from __future__ import annotations

from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _assert_no_decorator_syntax(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    for marker in (
        "@type_check",
        "@required_entity_signature",
        "@required_method",
        "@forbid_imports",
    ):
        assert marker not in text, f"Unexpected decorator syntax in {path}"


def test_public_docs_are_annotation_only() -> None:
    root = _repo_root()
    files = [
        root / "README.md",
        root / "docs" / "README.md",
        root / "docs" / "overview.md",
        root / "docs" / "usage-guide.md",
        root / "docs" / "api-reference.md",
        root / "docs" / "architecture.md",
        root / "docs" / "core-components.md",
        root / "example" / "project_1" / "README.md",
    ]
    combined = "\n".join(path.read_text(encoding="utf-8") for path in files)

    assert "__archtest__" in combined
    assert "Annotated[" in combined
    assert "signature" in combined.lower()
    assert "pythonarchtesting.rules" in combined
    assert "required_method(" in combined
    assert "forbid_imports(" in combined
    assert "pythonarchtesting.rules.compilation" in combined
    assert "pythonarchtesting.wrappers" not in combined
    assert "pythonarchtesting.core.compilation.decorators" not in combined
    assert "decorator-first" not in combined
    assert "decorated reference project" not in combined
    assert "preferred import-free syntax" not in combined.lower()
    assert "preferred import-free metadata" not in combined.lower()
    assert (
        "preferred fully static style is import-free tuple metadata"
        not in combined.lower()
    )
    assert "python -m pythonarchtesting.cli" in combined


def test_public_examples_and_default_reference_fixtures_are_annotation_first() -> None:
    root = _repo_root()
    files = [
        root / "README.md",
        root / "docs" / "README.md",
        root / "docs" / "overview.md",
        root / "docs" / "usage-guide.md",
        root / "docs" / "api-reference.md",
        root / "docs" / "architecture.md",
        root / "docs" / "core-components.md",
        root / "example" / "project_1" / "README.md",
        root / "example" / "project_1" / "reference" / "calculator.py",
        root / "example" / "project_1" / "reference" / "data_processor.py",
        root / "tests" / "fixtures" / "smoke" / "source" / "reference.py",
        root
        / "tests"
        / "fixtures"
        / "e2e"
        / "project_1"
        / "reference"
        / "calculator.py",
        root
        / "tests"
        / "fixtures"
        / "e2e"
        / "project_1"
        / "reference"
        / "data_processor.py",
    ]

    for path in files:
        _assert_no_decorator_syntax(path)


def test_example_project_readme_uses_current_cli_surface() -> None:
    root = _repo_root()
    text = (root / "example" / "project_1" / "README.md").read_text(encoding="utf-8")

    assert "python -m pythonarchtesting.cli" in text
    assert "--validate-declarations" in text
    assert "--targets-dir" in text
    assert "--format json" in text
    assert "--format markdown" in text
    assert "python -m pythonarchtesting --help" not in text
    assert "Decorator syntax remains supported" not in text


def test_example_project_reference_uses_current_rule_markers() -> None:
    root = _repo_root()
    calculator = (
        root / "example" / "project_1" / "reference" / "calculator.py"
    ).read_text(encoding="utf-8")
    data_processor = (
        root / "example" / "project_1" / "reference" / "data_processor.py"
    ).read_text(encoding="utf-8")

    assert (
        "from pythonarchtesting.rules import required_entity_signature, required_method"
        in calculator
    )
    assert "from src.rules" not in calculator
    assert ") -> Annotated[" in calculator
    assert (
        'required_entity_signature(mode="compatible", return_annotation="warning")'
        in calculator
    )
    assert "from pythonarchtesting.rules import forbid_imports" in data_processor
    assert "from src.rules" not in data_processor


def test_annotation_switch_notes_are_labeled_historical() -> None:
    root = _repo_root()
    files = [
        root / "docs" / "dev_notes" / "annotation_switch" / "README.md",
        root
        / "docs"
        / "dev_notes"
        / "annotation_switch"
        / "02_current_state_in_repo.md",
        root
        / "docs"
        / "dev_notes"
        / "annotation_switch"
        / "06_examples_and_limitations.md",
    ]

    for path in files:
        text = path.read_text(encoding="utf-8").lower()
        assert "historical" in text

    current_state = files[1].read_text(encoding="utf-8")
    assert "runtime_extract.py" in current_state
    assert "no longer present" in current_state
