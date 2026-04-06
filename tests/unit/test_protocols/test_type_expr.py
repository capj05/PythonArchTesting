from __future__ import annotations

import ast
from unittest.mock import patch

from src.protocols.type_expr import (
    annotated_base_and_metadata,
    annotated_details,
    classvar_inner_annotation,
    container_name,
    dotted_name,
    is_annotated_subscript,
    is_classvar_subscript,
    normalize_name_with_aliases,
    safe_unparse,
    unwrap_annotated_annotation_text,
)


def test_container_name_reconstructs_dotted_attribute_paths() -> None:
    node = ast.parse("typing_extensions.Annotated", mode="eval").body

    assert container_name(node) == "typing_extensions.Annotated"
    assert dotted_name(node) == "typing_extensions.Annotated"


def test_annotated_base_and_metadata_supports_plain_and_qualified_containers() -> None:
    plain = ast.parse('Annotated[Repo, "marker"]', mode="eval").body
    qualified = ast.parse('typing.Annotated[Repo, "marker"]', mode="eval").body

    assert isinstance(plain, ast.Subscript)
    assert isinstance(qualified, ast.Subscript)
    assert is_annotated_subscript(plain) is True
    assert is_annotated_subscript(qualified) is True
    plain_base, plain_metadata = annotated_base_and_metadata(plain)
    assert plain_base == "Repo"
    assert len(plain_metadata) == 1
    assert ast.unparse(plain_metadata[0]) == "'marker'"
    qualified_base, qualified_metadata = annotated_base_and_metadata(qualified)
    assert qualified_base == "Repo"
    assert len(qualified_metadata) == 1
    assert ast.unparse(qualified_metadata[0]) == "'marker'"


def test_normalize_name_with_aliases_rewrites_name_and_attribute_roots() -> None:
    aliased_name = ast.parse("RepoImpl", mode="eval").body
    aliased_attr = ast.parse("pkg.RepoImpl.Service", mode="eval").body

    assert (
        normalize_name_with_aliases(
            aliased_name,
            aliases={"RepoImpl": "app.Repository"},
        )
        == "app.Repository"
    )
    assert (
        normalize_name_with_aliases(
            aliased_attr,
            aliases={"pkg": "project.pkg"},
        )
        == "project.pkg.RepoImpl.Service"
    )


def test_classvar_helpers_detect_and_unwrap_supported_classvar_containers() -> None:
    plain = ast.parse("ClassVar[Repo]", mode="eval").body
    qualified = ast.parse("typing.ClassVar[Repo]", mode="eval").body

    assert isinstance(plain, ast.Subscript)
    assert isinstance(qualified, ast.Subscript)
    assert is_classvar_subscript(plain) is True
    assert is_classvar_subscript(qualified) is True
    assert classvar_inner_annotation(plain) == "Repo"
    assert classvar_inner_annotation(qualified) == "Repo"


def test_annotated_details_returns_shared_container_base_and_metadata() -> None:
    node = ast.parse('typing.Annotated[Repo, "marker", flag()]', mode="eval").body

    container, base, metadata = annotated_details(node)

    assert container == "typing.Annotated"
    assert base == "Repo"
    assert [ast.unparse(item) for item in metadata] == ["'marker'", "flag()"]


def test_unwrap_annotated_annotation_text_recursively_strips_supported_wrappers() -> (
    None
):
    node = ast.parse(
        'Annotated[typing.Annotated[Repo | None, "inner"], "outer"]', mode="eval"
    ).body

    assert unwrap_annotated_annotation_text(node) == "Repo | None"


def test_safe_unparse_returns_dump_when_unparse_fails() -> None:
    node = ast.parse("value", mode="eval").body

    with patch("ast.unparse", side_effect=ValueError("boom")):
        assert safe_unparse(node) == "Name('value', Load())"
