"""Canonical orchestration for rule compilation."""

from __future__ import annotations

from typing import Any, List, Tuple

from pythonarchtesting.config import Config
from pythonarchtesting.core.models import Evidence
from pythonarchtesting.entities import DeclarationEntry, Entity
from pythonarchtesting.rules.compilation.common import (
    canonicalize_payload,
    evidence_id,
)
from pythonarchtesting.rules.compilation.declarations import (
    declaration_rule_id_suffixes,
    is_invalid_annotation_declaration,
    normalize_declaration_entries,
)
from pythonarchtesting.rules.compilation.decorators.api_signature import (
    compile_required_entity_signature,
    compile_required_method,
)
from pythonarchtesting.rules.compilation.decorators.attributes import (
    compile_required_attribute,
)
from pythonarchtesting.rules.compilation.decorators.constructors import (
    compile_required_constructor,
)
from pythonarchtesting.rules.compilation.decorators.enum_type import compile_is_enum
from pythonarchtesting.rules.compilation.decorators.factories import (
    compile_required_factory,
)
from pythonarchtesting.rules.compilation.decorators.flow import compile_enforce_flow
from pythonarchtesting.rules.compilation.decorators.import_policy import (
    compile_forbid_imports,
)
from pythonarchtesting.rules.compilation.decorators.member_absence import (
    compile_does_not_have,
)
from pythonarchtesting.rules.compilation.decorators.nominal_type import (
    compile_exact_type,
    compile_inherits_directly_from,
    compile_not_subclass_of,
    compile_subclass_of,
)
from pythonarchtesting.rules.compilation.decorators.protocols import (
    compile_implements_protocol,
)


def _invalid_declaration_evidence(
    source_entity: Entity,
    declaration: DeclarationEntry,
) -> Evidence:
    payload = {
        "declaration": declaration.kind,
        "issue": "invalid_declaration",
        "raw": declaration.raw,
        "unsupported": declaration.unsupported,
        "base_annotation": declaration.base_annotation,
        "container": declaration.container,
    }
    location = {
        "filepath": source_entity.filepath_rel,
        "lineno": declaration.lineno or source_entity.lineno,
        "col": declaration.col,
    }
    return Evidence(
        evidence_id=evidence_id("compiler_invalid_declaration", payload),
        type="compiler_invalid_declaration",
        source="compiler",
        role="source",
        entity_id=source_entity.canonical_id,
        payload=canonicalize_payload(payload),
        location=location,
    )


def compile_rules(
    source_entities: List[Entity],
    cfg: Config,
) -> Tuple[List[Any], List[Any], List[Any]]:
    """Compile entity-scoped rules from annotation declarations."""
    declaration_compilers: dict[str, Any] = {
        "required_entity_signature": compile_required_entity_signature,
        "required_method": compile_required_method,
        "required_constructor": compile_required_constructor,
        "required_factory": compile_required_factory,
        "required_attribute": compile_required_attribute,
        "does_not_have": compile_does_not_have,
        "enforce_flow": compile_enforce_flow,
        "forbid_imports": compile_forbid_imports,
        "implements_protocol": compile_implements_protocol,
        "subclass_of": compile_subclass_of,
        "exact_type": compile_exact_type,
        "not_subclass_of": compile_not_subclass_of,
        "inherits_directly_from": compile_inherits_directly_from,
        "is_enum": compile_is_enum,
    }

    rules: List[Any] = []
    compiler_evidence: List[Any] = []
    compiler_results: List[Any] = []

    for source_entity in source_entities:
        declarations = normalize_declaration_entries(source_entity)
        valid_declarations: list[DeclarationEntry] = []

        for declaration in declarations:
            compiler = declaration_compilers.get(declaration.kind)
            if is_invalid_annotation_declaration(declaration):
                compiler_evidence.append(
                    _invalid_declaration_evidence(source_entity, declaration)
                )
                continue
            if compiler is None:
                continue
            valid_declarations.append(declaration)

        for declaration, rule_id_suffix in zip(
            valid_declarations,
            declaration_rule_id_suffixes(valid_declarations),
        ):
            compiler = declaration_compilers[declaration.kind]
            compiler_kwargs: dict[str, Any] = {"rule_id_suffix": rule_id_suffix}
            if declaration.kind in {
                "implements_protocol",
                "subclass_of",
                "exact_type",
                "not_subclass_of",
                "inherits_directly_from",
                "required_constructor",
            }:
                compiler_kwargs["source_entities"] = source_entities
            compiled_rules, evidence_items, results = compiler(
                source_entity,
                declaration,
                cfg,
                **compiler_kwargs,
            )
            rules.extend(compiled_rules)
            compiler_evidence.extend(evidence_items)
            compiler_results.extend(results)

    rules = sorted(rules, key=lambda r: (r.rule_id, r.selector.source_entity_id))
    compiler_results = sorted(
        compiler_results, key=lambda r: (r.rule_id, r.source_entity_id)
    )
    return rules, compiler_evidence, compiler_results


__all__ = ["compile_rules"]
