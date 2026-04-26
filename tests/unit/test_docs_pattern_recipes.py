from __future__ import annotations

import re
from pathlib import Path

from pythonarchtesting.rules import __all__ as public_rule_markers


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _slugify(text: str) -> str:
    slug = text.strip().lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    return slug.strip("-")


def test_pattern_recipe_catalog_references_existing_snippets() -> None:
    root = _repo_root()
    catalog = (root / "docs" / "pattern-recipes.md").read_text(encoding="utf-8")
    snippet_paths = re.findall(r"docs/snippets/patterns/[a-z_]+\.py", catalog)

    assert snippet_paths == [
        "docs/snippets/patterns/immutable_value_object.py",
        "docs/snippets/patterns/enum_domain_type.py",
        "docs/snippets/patterns/repository_contract.py",
        "docs/snippets/patterns/lifecycle_hooks.py",
    ]

    for relative_path in snippet_paths:
        assert (root / relative_path).exists(), f"Missing snippet: {relative_path}"


def test_pattern_recipe_index_links_resolve_to_sections() -> None:
    catalog = (_repo_root() / "docs" / "pattern-recipes.md").read_text(
        encoding="utf-8"
    )
    headings = re.findall(r"^## (.+)$", catalog, flags=re.MULTILINE)
    heading_slugs = {_slugify(heading) for heading in headings}
    index_links = re.findall(r"\(#([a-z0-9-]+)\)", catalog)

    assert "recipe-index" not in index_links
    assert heading_slugs
    assert index_links

    for anchor in index_links:
        assert anchor in heading_slugs, f"Broken recipe anchor: {anchor}"


def test_pattern_recipe_markers_are_public_and_documented() -> None:
    root = _repo_root()
    catalog = (root / "docs" / "pattern-recipes.md").read_text(encoding="utf-8")
    api_reference = (root / "docs" / "api-reference.md").read_text(encoding="utf-8")

    markers = {
        "required_attribute",
        "required_constructor",
        "does_not_have",
        "is_enum",
        "required_method",
        "required_factory",
        "require_method_set",
        "implements_protocol",
    }

    for marker in markers:
        assert marker in public_rule_markers
        assert f"`{marker}(...)" in catalog
        assert f"`{marker}(...)" in api_reference


def test_api_reference_links_to_pattern_catalog() -> None:
    text = (_repo_root() / "docs" / "api-reference.md").read_text(encoding="utf-8")

    assert "pattern-recipes.md" in text
    assert "Pattern recipes and copy-ready examples" in text
