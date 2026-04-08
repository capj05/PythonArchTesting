from __future__ import annotations

import pythonarchtesting.protocol_support as protocol_support
from pythonarchtesting import protocols


def test_protocol_support_reexports_protocol_public_api() -> None:
    assert protocol_support.__all__ == [
        "ProtocolAttribute",
        "ReferenceResolution",
        "class_attributes",
        "class_methods",
        "import_aliases_for_entity",
        "is_protocol_entity",
        "module_entity_for",
        "normalize_reference",
        "protocol_attributes",
        "protocol_methods",
        "resolve_reference",
        "signature_subject_annotation",
    ]

    for name in protocol_support.__all__:
        assert getattr(protocol_support, name) is getattr(protocols, name)
