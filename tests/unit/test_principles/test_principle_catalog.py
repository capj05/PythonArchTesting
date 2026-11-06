from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from pythonarchtesting.principles import (
    CatalogError,
    Principle,
    UnknownPrincipleError,
    fact_signature,
    get_principle,
    load_catalog,
    signature_matches,
)

PYPROJECT = Path(__file__).parents[3] / "pyproject.toml"

_VALID = """
id = "demo"
name = "Demo principle"
level = "basic"
summary = '''
First sentence of the summary.
Second one.
'''
why = "Because."

[roles]
logic = "the functions that compute"

[[checks]]
role = "logic"
marker = "forbid_runtime_calls"
modules = ["builtins.print"]
transitive = true
cases = "an ordinary input"

[[errors]]
id = "print_in_logic"
title = "prints"
detected_by = "forbid_runtime_calls"
what = "Function `{function}` calls `{callee_short}`."
why = "Return it."
fix = "Use return."
signature = { kind = "call", callee = "builtins:print", via = false }

[[errors]]
id = "read_private"
title = "reads a private attribute"
gap = "G1"
why = "Internal."
fix = "Use a method."

[[neutral]]
id = "style_noise"
title = "poor style"

[[gaps]]
id = "G1"
title = "not checked"
detail = "No marker sees it."
"""


def _write(directory: Path, text: str, name: str = "demo") -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{name}.toml").write_text(text, encoding="utf-8")
    return directory


def test_packaged_catalogue_holds_both_principles():
    catalogue = load_catalog()
    assert sorted(catalogue) == ["encapsulation", "io_separation"]
    assert all(isinstance(p, Principle) for p in catalogue.values())


def test_get_principle_returns_the_entry():
    principle = get_principle("io_separation")
    assert principle.id == "io_separation"
    assert principle.level == "basic"
    assert {error.id for error in principle.errors} >= {"print_instead_of_return"}
    print_error = next(e for e in principle.errors if e.id == "print_instead_of_return")
    assert print_error.signature is not None
    assert print_error.signature.as_dict() == {
        "kind": "call",
        "callee": "builtins:print",
        "via": False,
    }


def test_get_unknown_principle_names_the_known_ones():
    with pytest.raises(UnknownPrincipleError, match="encapsulation"):
        get_principle("encapsulaton")


def test_catalogue_texts_are_english_and_single_line():
    for principle in load_catalog().values():
        for text in (principle.summary, principle.why, principle.name):
            assert "\n" not in text
            assert not set(text) & set("áčďéěíňóřšťúůýž"), text


def test_principles_are_immutable():
    principle = get_principle("encapsulation")
    with pytest.raises(AttributeError):
        principle.name = "x"  # type: ignore[misc]
    with pytest.raises(TypeError):
        principle.roles["owner"] = "x"  # type: ignore[index]


def test_to_dict_is_json_and_omits_missing_fields():
    data = get_principle("encapsulation").to_dict()
    assert json.loads(json.dumps(data)) == data
    errors = {error["id"]: error for error in data["errors"]}
    assert "gap" not in errors["bypass_method"]
    assert errors["bypass_method"]["signature"]["private"] is True
    assert errors["read_private"]["gap"] == "G2"
    assert "detected_by" not in errors["read_private"]
    assert "signature" not in errors["read_private"]
    assert data["gaps"][0]["id"] == "G2"


def test_load_catalog_from_a_directory(tmp_path: Path):
    catalogue = load_catalog(_write(tmp_path, _VALID))
    principle = catalogue["demo"]
    assert principle.summary == "First sentence of the summary. Second one."
    assert principle.brief == "First sentence of the summary."
    assert principle.checks[0].modules == ("builtins.print",)
    assert principle.checks[0].transitive is True
    assert principle.neutral[0].title == "poor style"
    assert principle.gaps[0].detail == "No marker sees it."


@pytest.mark.parametrize(
    ("old", "new", "message"),
    [
        ('name = "Demo principle"\n', "", "missing key 'name'"),
        ('level = "basic"', 'level = "basic"\ncolour = "red"', "unknown key 'colour'"),
        ('why = "Because."', "why = 3", "'why' must be a string"),
        ('role = "logic"', 'role = "ui"', "role 'ui'"),
        (
            'detected_by = "forbid_runtime_calls"',
            'detected_by = "forbid_imports"',
            "'forbid_imports' is not the marker of any check",
        ),
        ('gap = "G1"', 'gap = "G9"', "gap 'G9'"),
        ('gap = "G1"', "", "either 'detected_by' or 'gap'"),
        ("`{callee_short}`", "`{callee_name}`", "placeholder 'callee_name'"),
        ('kind = "call"', 'kind = "phone"', "kind 'phone'"),
        (
            'callee = "builtins:print", via = false',
            'callee = "builtins:print", via = "no"',
            "'via' must be a boolean",
        ),
        (
            'kind = "call", callee',
            'kind = "call", change = "mutated", callee',
            "'change' applies only to kind 'write'",
        ),
        (
            'id = "style_noise"',
            'id = "print_in_logic"',
            "duplicate id 'print_in_logic'",
        ),
        (
            'id = "print_in_logic"',
            'id = "syntax_error"',
            "error id 'syntax_error' is reserved for the tool",
        ),
    ],
)
def test_malformed_entry_is_a_clear_error(
    tmp_path: Path, old: str, new: str, message: str
):
    assert old in _VALID
    text = _VALID.replace(old, new, 1)
    with pytest.raises(CatalogError, match="demo.toml") as raised:
        load_catalog(_write(tmp_path, text))
    assert message in str(raised.value)


def test_detected_error_needs_what_and_signature(tmp_path: Path):
    text = _VALID.replace(
        'signature = { kind = "call", callee = "builtins:print", via = false }\n', ""
    )
    with pytest.raises(CatalogError, match="missing key 'signature'"):
        load_catalog(_write(tmp_path, text))


def test_file_name_must_match_the_id(tmp_path: Path):
    with pytest.raises(CatalogError, match="other.toml.*'demo'"):
        load_catalog(_write(tmp_path, _VALID, name="other"))


def test_invalid_toml_is_a_catalog_error(tmp_path: Path):
    with pytest.raises(CatalogError, match="demo.toml"):
        load_catalog(_write(tmp_path, "id = "))


def test_fact_signature_reduces_a_fact():
    call = {
        "kind": "call",
        "callee": "builtins:print",
        "caller": "grades:average",
        "via": ["messages:warn"],
        "line": 5,
    }
    assert fact_signature(call) == {
        "kind": "call",
        "callee": "builtins:print",
        "via": True,
    }
    write = {"kind": "write", "change": "assigned", "attribute": "_stock", "class": "X"}
    assert fact_signature(write) == {
        "kind": "write",
        "change": "assigned",
        "via": False,
        "private": True,
    }


def test_pyproject_ships_the_catalogue_and_tomli():
    if sys.version_info >= (3, 11):
        import tomllib
    else:
        tomllib = pytest.importorskip("tomli")
    data = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    assert (
        "principles/catalog/*.toml"
        in data["tool"]["setuptools"]["package-data"]["pythonarchtesting"]
    )
    assert 'tomli>=2; python_version < "3.11"' in data["project"]["dependencies"]


_SECOND_ERROR = """
[[errors]]
id = "print_again"
title = "prints again"
detected_by = "forbid_runtime_calls"
what = "Function `{function}` prints."
why = "Return it."
fix = "Use return."
signature = { kind = "call", callee = "builtins:print", via = false }
"""


def test_unknown_marker_is_rejected(tmp_path: Path):
    text = _VALID.replace("forbid_runtime_calls", "forbid_runtime_cals")
    with pytest.raises(CatalogError, match="marker 'forbid_runtime_cals' is not"):
        load_catalog(_write(tmp_path, text))


def test_signature_kind_the_marker_never_emits_is_rejected(tmp_path: Path):
    text = _VALID.replace(
        'signature = { kind = "call", callee = "builtins:print", via = false }',
        'signature = { kind = "write", change = "mutated" }',
    )
    with pytest.raises(
        CatalogError, match="'forbid_runtime_calls' never reports kind 'write'"
    ):
        load_catalog(_write(tmp_path, text))


def test_two_errors_with_the_same_signature_are_ambiguous(tmp_path: Path):
    text = _VALID.replace("[[neutral]]", _SECOND_ERROR + "\n[[neutral]]", 1)
    with pytest.raises(
        CatalogError, match="'print_again' has the signature of 'print_in_logic'"
    ):
        load_catalog(_write(tmp_path, text))


def test_target_role_must_name_a_declared_role(tmp_path: Path):
    text = _VALID.replace("transitive = true", 'target_role = "ui"')
    with pytest.raises(CatalogError, match="target_role 'ui' is not one of the"):
        load_catalog(_write(tmp_path, text))


def test_target_role_is_kept(tmp_path: Path):
    text = _VALID.replace("transitive = true", 'target_role = "logic"')
    principle = load_catalog(_write(tmp_path, text))["demo"]
    assert principle.checks[0].target_role == "logic"
    assert principle.checks[0].to_dict()["target_role"] == "logic"


@pytest.mark.parametrize(
    ("old", "new", "message"),
    [
        (
            'callee = "builtins:print"',
            'callee = "builtins.print"',
            "callee 'builtins.print' must be 'module:name'",
        ),
        (
            'callee = "builtins:print"',
            'callee = "builtins:print:x"',
            "callee 'builtins:print:x' must be 'module:name'",
        ),
        (
            'modules = ["builtins.print"]',
            'modules = ["builtins:print"]',
            "module 'builtins:print' must be a dotted name",
        ),
    ],
)
def test_callee_and_modules_keep_their_notation(
    tmp_path: Path, old: str, new: str, message: str
):
    with pytest.raises(CatalogError) as raised:
        load_catalog(_write(tmp_path, _VALID.replace(old, new, 1)))
    assert message in str(raised.value)


def test_brief_does_not_cut_at_abbreviations(tmp_path: Path):
    text = _VALID.replace(
        "First sentence of the summary.",
        "First, e.g. this, i.e. that, ends here.",
    )
    principle = load_catalog(_write(tmp_path, text))["demo"]
    assert principle.brief == "First, e.g. this, i.e. that, ends here."


def test_signature_matches_on_declared_keys_only():
    declared = {"kind": "call", "callee": "io:open"}
    assert signature_matches(
        declared, {"kind": "call", "callee": "io:open", "via": True}
    )
    assert not signature_matches(declared, {"kind": "call", "callee": "builtins:print"})
    assert not signature_matches(declared, {"kind": "call"})


def test_packaged_catalogue_names_no_task():
    for principle in load_catalog().values():
        text = json.dumps(principle.to_dict()).casefold()
        for word in ("inventory", "grades", "shop", "stock", "history"):
            assert word not in text, (principle.id, word)


def test_an_error_may_name_a_mutation_operator(tmp_path: Path):
    signature = (
        'signature = { kind = "call", callee = "builtins:print", via = false }\n'
    )
    text = _VALID.replace(signature, signature + 'operator = "add_io_call"\n', 1)

    entry = load_catalog(_write(tmp_path, text))["demo"]

    assert entry.errors[0].operator == "add_io_call"
    assert entry.errors[0].to_dict()["operator"] == "add_io_call"


def test_an_unknown_mutation_operator_is_rejected(tmp_path: Path):
    signature = (
        'signature = { kind = "call", callee = "builtins:print", via = false }\n'
    )
    text = _VALID.replace(signature, signature + 'operator = "add_print"\n', 1)

    with pytest.raises(CatalogError, match="operator 'add_print' is not one of"):
        load_catalog(_write(tmp_path, text))


def test_packaged_operators_seed_their_errors():
    seeded = {
        (principle.id, error.id): error.operator
        for principle in load_catalog().values()
        for error in principle.errors
        if error.operator
    }
    assert seeded == {
        ("io_separation", "print_instead_of_return"): "add_io_call",
        ("io_separation", "input_in_logic"): "add_io_call",
        ("io_separation", "file_io_in_logic"): "add_io_call",
        ("encapsulation", "replace_attribute"): "foreign_write",
    }
