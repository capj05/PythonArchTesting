"""
Tests for signature normalization.
"""

import ast

from src.entities import signature_key_from_info
from src.entities_extraction import signature_info_from_ast


def test_signature_info_from_ast() -> None:
    source = "def f(a, /, b, c=1, *, d, e=2, **kwargs):\n    return None\n"
    tree = ast.parse(source)
    fn = tree.body[0]
    info = signature_info_from_ast(fn)

    assert info.posonly == 1
    assert info.pos == 2
    assert info.vararg is False
    assert info.kwonly == 2
    assert info.kwarg is True
    assert info.defaults == 1
    assert info.kw_defaults == 1

    key = signature_key_from_info(info)
    assert key == "p1-a2-v0-k2-w1-d1-kd1"


def test_signature_info_method() -> None:
    source = "def m(self, x):\n    return x\n"
    tree = ast.parse(source)
    fn = tree.body[0]
    info = signature_info_from_ast(fn)

    assert info.pos == 2
    assert signature_key_from_info(info) == "p0-a2-v0-k0-w0-d0-kd0"
