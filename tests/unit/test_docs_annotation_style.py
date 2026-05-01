from __future__ import annotations

from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _assert_no_decorator_syntax(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    for marker in (
        "@type_check",
        "@required_entity_signature",
        "@required_factory",
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
        root / "docs" / "pattern-recipes.md",
        root / "docs" / "architecture.md",
        root / "docs" / "core-components.md",
    ]
    combined = "\n".join(path.read_text(encoding="utf-8") for path in files)

    assert "__archtest__" in combined
    assert "Annotated[" in combined
    assert "signature" in combined.lower()
    assert "pythonarchtesting.rules" in combined
    assert "required_method(" in combined
    assert "required_factory(" in combined
    assert "does_not_have(" in combined
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
        root / "docs" / "pattern-recipes.md",
        root / "docs" / "architecture.md",
        root / "docs" / "core-components.md",
        root / "docs" / "snippets" / "patterns" / "immutable_value_object.py",
        root / "docs" / "snippets" / "patterns" / "enum_domain_type.py",
        root / "docs" / "snippets" / "patterns" / "repository_contract.py",
        root / "docs" / "snippets" / "patterns" / "lifecycle_hooks.py",
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


def test_public_docs_use_current_cli_surface() -> None:
    root = _repo_root()
    text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (
            root / "README.md",
            root / "docs" / "usage-guide.md",
        )
    )

    assert "--validate-declarations" in text
    assert "--targets-dir" in text
    assert "--format json" in text
    assert "--format markdown" in text
    assert "python -m pythonarchtesting.cli" in text or "python-arch-test" in text
    assert "example/checkout_assignment/reference" in text
    assert "example/checkout_assignment/assignments" in text
    assert "python -m pythonarchtesting --help" not in text


def test_tracked_reference_fixtures_use_current_rule_markers() -> None:
    root = _repo_root()
    calculator = (
        root
        / "tests"
        / "fixtures"
        / "e2e"
        / "project_1"
        / "reference"
        / "calculator.py"
    ).read_text(encoding="utf-8")
    data_processor = (
        root
        / "tests"
        / "fixtures"
        / "e2e"
        / "project_1"
        / "reference"
        / "data_processor.py"
    ).read_text(encoding="utf-8")

    assert "from pythonarchtesting.rules import" in calculator
    assert "required_entity_signature" in calculator
    assert "required_method" in calculator
    assert "from src.rules" not in calculator
    assert "__archtest__: Annotated[" in calculator
    assert (
        'required_entity_signature(mode="compatible", return_annotation="warning")'
        in calculator
    )
    assert "from pythonarchtesting.rules import forbid_imports" in data_processor
    assert "from src.rules" not in data_processor


def test_api_reference_documents_neg001_v2_options() -> None:
    root = _repo_root()
    text = (root / "docs" / "api-reference.md").read_text(encoding="utf-8")
    neg001_section = text.split("### `does_not_have(...)`", 1)[1].split(
        "### `forbid_imports(...)`",
        1,
    )[0]

    assert "NEG001/does_not_have/v1" in neg001_section
    assert 'name_match="alias"' in neg001_section
    assert 'name_match="regex"' in neg001_section
    assert 'signature_mode="exact"' in neg001_section
    assert "include_dynamic_attributes=True" in neg001_section
    assert "include_descriptors" in neg001_section
    assert "not supported in v1" not in neg001_section
