"""Assisted pairing: the mapping file and the signature check."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pythonarchtesting.entities import SignatureInfo
from pythonarchtesting.matching.assisted import load_mapping, signature_compatible


def _sig(pos: int, defaults: int = 0, vararg: bool = False) -> SignatureInfo:
    return SignatureInfo(
        posonly=0,
        pos=pos,
        vararg=vararg,
        kwonly=0,
        kwarg=False,
        defaults=defaults,
        kw_defaults=0,
    )


@pytest.mark.parametrize(
    ("source", "target", "ok"),
    [
        (_sig(2), _sig(2), True),
        (_sig(2), _sig(3, defaults=1), True),
        (_sig(2), _sig(1), False),
        (_sig(2), _sig(3), False),
        (_sig(2), _sig(0, vararg=True), True),
    ],
)
def test_signature_compatible(source: SignatureInfo, target: SignatureInfo, ok: bool):
    assert signature_compatible(source, target) is ok


def test_load_mapping_for_all_and_for_one_target(tmp_path: Path):
    path = tmp_path / "m.json"
    path.write_text(
        json.dumps({"pairs": {"a": "b"}, "targets": {"t1": {"pairs": {"c": "d"}}}}),
        encoding="utf-8",
    )

    assert load_mapping(path) == {"*": {"a": "b"}, "t1": {"c": "d"}}


@pytest.mark.parametrize(
    "data", [[], {}, {"pairs": {"a": 1}}, {"targets": {"t": {}}}, {"pairs": {"": "b"}}]
)
def test_load_mapping_rejects_malformed_files(tmp_path: Path, data: object):
    path = tmp_path / "m.json"
    path.write_text(json.dumps(data), encoding="utf-8")

    with pytest.raises(ValueError):
        load_mapping(path)


def test_load_mapping_rejects_targets_that_are_not_an_object(tmp_path: Path):
    path = tmp_path / "m.json"
    path.write_text(json.dumps({"targets": [1]}), encoding="utf-8")

    with pytest.raises(ValueError, match="targets"):
        load_mapping(path)


def test_a_required_keyword_only_parameter_of_the_target_is_incompatible():
    source = _sig(2)
    required_kw = SignatureInfo(
        posonly=0, pos=2, vararg=False, kwonly=1, kwarg=False, defaults=0, kw_defaults=0
    )
    optional_kw = SignatureInfo(
        posonly=0, pos=2, vararg=False, kwonly=1, kwarg=False, defaults=0, kw_defaults=1
    )

    assert signature_compatible(source, required_kw) is False
    assert signature_compatible(source, optional_kw) is True
