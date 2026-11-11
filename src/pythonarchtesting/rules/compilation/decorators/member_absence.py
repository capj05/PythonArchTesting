from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable, List, Tuple

from pythonarchtesting.config import Config
from pythonarchtesting.core.models import Evidence
from pythonarchtesting.entities import DeclarationEntry, Entity, build_canonical_id

from ..common import (
    build_invalid_param_sentinel_rule,
    declaration_evidence,
    invalid_target_evidence,
    marker_severity,
    with_rule_id_suffix,
)
from .method_set import InvalidParam

_VALID_MEMBER_KINDS = {"any", "method", "attribute", "property"}
_VALID_STORAGE_VALUES = {"any", "instance", "class"}
_VALID_NAME_MATCH = {"exact", "alias", "regex"}
_VALID_SIGNATURE_MODES = {"any", "compatible", "exact"}
_SENTINEL_RULE_ID_PREFIX = "NEG001/does_not_have/invalid_declaration"
_INVALID_TARGET_ISSUE = "compiler_invalid_target"
_V2_PARAM_KEYS = frozenset(
    {
        "aliases",
        "include_descriptors",
        "include_dynamic_attributes",
        "name_match",
        "pattern",
        "signature_mode",
    }
)


def _invalid_declaration(
    source_entity: Entity,
    declaration: DeclarationEntry,
    *,
    issue: str,
    **payload_extra: Any,
) -> Evidence:
    payload = {
        "declaration": "does_not_have",
        "issue": issue,
        **payload_extra,
    }
    return declaration_evidence(
        source_entity,
        declaration,
        evidence_type="compiler_invalid_member_absence_declaration",
        payload=payload,
    )


def _enclosing_class_qualname(entity: Entity) -> str | None:
    if entity.kind != "method" or "." not in entity.qualname:
        return None
    return entity.qualname.rsplit(".", 1)[0]


def _owning_class_id(method_entity: Entity) -> str | None:
    class_qualname = _enclosing_class_qualname(method_entity)
    if class_qualname is None:
        return None
    return build_canonical_id(
        method_entity.role,
        method_entity.root_label,
        method_entity.module_path,
        class_qualname,
        "class",
        "-",
    )


def _normalized_aliases(value: Any) -> list[str] | None:
    if value is None:
        return None
    if not isinstance(value, list):
        return None
    aliases = [str(alias).strip() for alias in value]
    if any(not alias for alias in aliases):
        return None
    return aliases


@dataclass(frozen=True)
class _Problem:
    """Why the compiler drops a ``does_not_have`` declaration.

    ``invalid`` is what the sentinel rule reports; ``issue`` and ``payload``
    are the issue and the extra payload keys of the compiler evidence. The
    issue ``compiler_invalid_target`` is reported with the shared target
    evidence instead, which ignores ``payload``.
    """

    invalid: InvalidParam
    issue: str
    payload: dict[str, Any] = field(default_factory=dict)


def _problem(
    issue: str,
    *,
    param: str,
    value: Any,
    valid: list[str] | None,
    reason: str,
    **payload: Any,
) -> _Problem:
    """A problem from the sentinel's fields and the evidence's issue and payload."""
    return _Problem(
        invalid=InvalidParam(param=param, value=value, valid=valid, reason=reason),
        issue=issue,
        payload=payload,
    )


@dataclass(frozen=True)
class _Declared:
    """The parameters of a ``does_not_have`` declaration, normalised.

    Normalising has no side effects and cannot fail on the literal values a
    declaration carries, so it is done once for all parameters, before any of
    them is checked. ``raw_name`` and ``raw_aliases`` keep the
    values as declared, because the evidence of an invalid one reports them
    as they were; ``pattern`` is kept as declared throughout.
    """

    raw_name: Any
    name: str | None
    member_kind: str
    storage: str
    name_match: str
    raw_aliases: Any
    aliases: list[str] | None
    pattern: Any
    signature_mode: str
    include_descriptors: bool
    include_dynamic_attributes: bool

    @classmethod
    def parse(cls, params: dict[str, Any]) -> _Declared:
        """Normalise ``params``: the keyword values lower-cased, the name and
        aliases stripped, the two ``include_*`` options read as truth values."""
        raw_name = params.get("name")
        return cls(
            raw_name=raw_name,
            name=raw_name.strip() if isinstance(raw_name, str) else None,
            member_kind=str(params.get("member_kind", "any")).lower(),
            storage=str(params.get("storage", "any")).lower(),
            name_match=str(params.get("name_match", "exact")).lower(),
            raw_aliases=params.get("aliases"),
            aliases=_normalized_aliases(params.get("aliases")),
            pattern=params.get("pattern"),
            signature_mode=str(params.get("signature_mode", "any")).lower(),
            include_descriptors=bool(params.get("include_descriptors", False)),
            include_dynamic_attributes=bool(
                params.get("include_dynamic_attributes", False)
            ),
        )


def _validate_placement(
    source_entity: Entity, declaration: DeclarationEntry
) -> _Problem | None:
    """The marker must sit in the body of a class or of a method."""
    if declaration.surface != "body":
        return _problem(
            "compiler_invalid_surface",
            param="declaration_surface",
            value=declaration.surface,
            valid=["body"],
            reason="does_not_have must be declared on a class or method body",
            expected_surface="body",
            found_surface=declaration.surface,
        )
    if source_entity.kind not in {"class", "method"}:
        return _problem(
            _INVALID_TARGET_ISSUE,
            param="target_kind",
            value=source_entity.kind,
            valid=["class", "method"],
            reason="does_not_have must target a class or method",
        )
    return None


def _validate_name(declared: _Declared) -> _Problem | None:
    """A declared name must be a non-empty string; it may also be absent."""
    raw_name = declared.raw_name
    if raw_name is not None and (not isinstance(raw_name, str) or not raw_name.strip()):
        return _problem(
            "invalid_name",
            param="name",
            value=raw_name,
            valid=None,
            reason="name must be a non-empty string",
            name=raw_name,
        )
    return None


def _validate_kinds(declared: _Declared) -> _Problem | None:
    """The member kind and storage must be known, and only attributes (or
    any member) may be restricted to one storage."""
    member_kind, storage = declared.member_kind, declared.storage
    if member_kind not in _VALID_MEMBER_KINDS:
        return _problem(
            "invalid_member_kind",
            param="member_kind",
            value=member_kind,
            valid=sorted(_VALID_MEMBER_KINDS),
            reason="member_kind must be one of: any, method, attribute, property",
            member_kind=member_kind,
        )
    if storage not in _VALID_STORAGE_VALUES:
        return _problem(
            "invalid_storage",
            param="storage",
            value=storage,
            valid=sorted(_VALID_STORAGE_VALUES),
            reason="storage must be one of: any, instance, class",
            storage=storage,
        )
    if member_kind in {"method", "property"} and storage != "any":
        return _problem(
            "invalid_storage_for_member_kind",
            param="storage",
            value=storage,
            valid=["any"],
            reason=(f"storage must be 'any' when member_kind is '{member_kind}'"),
            member_kind=member_kind,
            storage=storage,
        )
    return None


def _no_aliases(declared: _Declared, name_match: str) -> _Problem | None:
    """Aliases are refused by ``name_match`` values that do not use them."""
    if declared.aliases not in (None, []):
        return _problem(
            f"aliases_not_allowed_for_{name_match}_name_match",
            param="aliases",
            value=declared.aliases,
            valid=None,
            reason=f"aliases are not allowed when name_match='{name_match}'",
        )
    return None


def _no_pattern(declared: _Declared, name_match: str) -> _Problem | None:
    """A pattern is refused by ``name_match`` values that do not use it."""
    if declared.pattern is not None:
        return _problem(
            f"pattern_not_allowed_for_{name_match}_name_match",
            param="pattern",
            value=declared.pattern,
            valid=None,
            reason=f"pattern is not allowed when name_match='{name_match}'",
        )
    return None


def _validate_exact_match(declared: _Declared) -> _Problem | None:
    """An exact match takes neither aliases nor a pattern."""
    return _no_aliases(declared, "exact") or _no_pattern(declared, "exact")


def _validate_alias_match(declared: _Declared) -> _Problem | None:
    """An alias match needs aliases and takes no pattern."""
    if not declared.aliases:
        return _problem(
            "missing_aliases",
            param="aliases",
            value=declared.aliases,
            valid=None,
            reason="aliases are required when name_match='alias'",
        )
    return _no_pattern(declared, "alias")


def _validate_regex_match(declared: _Declared) -> _Problem | None:
    """A regex match takes no aliases and needs a pattern that compiles.

    The pattern is compiled stripped, as the rule keeps it, so that a
    pattern which compiles only with its surrounding whitespace (``"a\\ "``)
    is dropped here and not left to fail when the rule is evaluated. The
    problems report the pattern as declared.
    """
    problem = _no_aliases(declared, "regex")
    if problem is not None:
        return problem
    pattern = declared.pattern
    if not isinstance(pattern, str) or not pattern.strip():
        return _problem(
            "missing_pattern",
            param="pattern",
            value=pattern,
            valid=None,
            reason="pattern is required when name_match='regex'",
        )
    try:
        re.compile(pattern.strip())
    except re.error as exc:
        return _problem(
            "invalid_pattern",
            param="pattern",
            value=pattern,
            valid=None,
            reason=f"pattern is not a valid regex: {exc}",
            pattern=pattern,
            error=str(exc),
        )
    return None


_NAME_MATCH_VALIDATORS: dict[str, Callable[[_Declared], _Problem | None]] = {
    "exact": _validate_exact_match,
    "alias": _validate_alias_match,
    "regex": _validate_regex_match,
}


def _validate_name_match(declared: _Declared) -> _Problem | None:
    """The name match must be known, the aliases and pattern well-formed, and
    then fit the name match: the types are checked before the combination."""
    if declared.name_match not in _VALID_NAME_MATCH:
        return _problem(
            "invalid_name_match",
            param="name_match",
            value=declared.name_match,
            valid=sorted(_VALID_NAME_MATCH),
            reason="name_match must be one of: exact, alias, regex",
            name_match=declared.name_match,
        )
    if declared.raw_aliases is not None and declared.aliases is None:
        return _problem(
            "invalid_aliases",
            param="aliases",
            value=declared.raw_aliases,
            valid=None,
            reason="aliases must be a list of non-empty strings",
            aliases=declared.raw_aliases,
        )
    if declared.pattern is not None and not isinstance(declared.pattern, str):
        return _problem(
            "invalid_pattern",
            param="pattern",
            value=declared.pattern,
            valid=None,
            reason="pattern must be a string",
            pattern=declared.pattern,
        )
    return _NAME_MATCH_VALIDATORS[declared.name_match](declared)


def _method_only_option(
    option: str, switched_on: bool, member_kind: str
) -> _Problem | None:
    """``option`` (an ``include_*`` flag) may not be switched on for methods.

    The sentinel reports the switched-on option as ``True`` and offers the
    string ``"False"``, as it always has.
    """
    if switched_on and member_kind == "method":
        return _problem(
            f"{option}_not_supported_for_method_kind",
            param=option,
            value=True,
            valid=["False"],
            reason=f"{option} is not supported when member_kind='method'",
            member_kind=member_kind,
        )
    return None


def _validate_signature_options(declared: _Declared) -> _Problem | None:
    """The signature mode must be known and only compare methods (or any
    member); the ``include_*`` options do not apply to methods."""
    signature_mode, member_kind = declared.signature_mode, declared.member_kind
    if signature_mode not in _VALID_SIGNATURE_MODES:
        return _problem(
            "invalid_signature_mode",
            param="signature_mode",
            value=signature_mode,
            valid=sorted(_VALID_SIGNATURE_MODES),
            reason="signature_mode must be one of: any, compatible, exact",
            signature_mode=signature_mode,
        )
    if signature_mode != "any" and member_kind not in {"method", "any"}:
        return _problem(
            "invalid_signature_mode_for_member_kind",
            param="signature_mode",
            value=signature_mode,
            valid=["any"],
            reason=(
                f"signature_mode must be 'any' when member_kind is '{member_kind}'"
            ),
            signature_mode=signature_mode,
            member_kind=member_kind,
        )
    return _method_only_option(
        "include_descriptors", declared.include_descriptors, member_kind
    ) or _method_only_option(
        "include_dynamic_attributes", declared.include_dynamic_attributes, member_kind
    )


def _validate_method_body(
    source_entity: Entity, declared: _Declared
) -> _Problem | None:
    """On a method body the marker forbids that method in its class, so the
    member kind must allow methods and the method must have a class; on a
    class body there is no method whose signature could be compared."""
    if source_entity.kind == "method":
        if declared.member_kind not in {"method", "any"}:
            return _problem(
                "invalid_member_kind_for_method_body",
                param="member_kind",
                value=declared.member_kind,
                valid=["method", "any"],
                reason=(
                    "member_kind must be 'method' or 'any' when declared on a method body"
                ),
                member_kind=declared.member_kind,
            )
        if not _owning_class_id(source_entity):
            return _problem(
                "missing_owning_class_for_method_body",
                param="target_kind",
                value="orphan_method",
                valid=None,
                reason="does_not_have on a method requires an owning class",
            )
        return None
    if declared.signature_mode != "any":
        return _problem(
            "signature_mode_requires_method_body",
            param="signature_mode",
            value=declared.signature_mode,
            valid=["any"],
            reason=(
                "signature_mode != 'any' requires the declaration to be on a method body"
            ),
            signature_mode=declared.signature_mode,
        )
    return None


def _member_name(source_entity: Entity, declared: _Declared) -> str | None:
    """The forbidden member's name: the declared one, else on a method body
    the method's own name."""
    if declared.name is None and source_entity.kind == "method":
        return source_entity.name
    return declared.name


def _validate_exact_name(source_entity: Entity, declared: _Declared) -> _Problem | None:
    """An exact match needs a name, declared or taken from the method body."""
    if declared.name_match == "exact" and _member_name(source_entity, declared) is None:
        return _problem(
            "invalid_name",
            param="name",
            value=None,
            valid=None,
            reason="name is required when name_match='exact'",
            name=declared.raw_name,
        )
    return None


def _validate_declared(source_entity: Entity, declared: _Declared) -> _Problem | None:
    """The first problem of the parameters, in the order the compiler has
    always checked them: the order decides which problem is reported."""
    return (
        _validate_name(declared)
        or _validate_kinds(declared)
        or _validate_name_match(declared)
        or _validate_signature_options(declared)
        or _validate_method_body(source_entity, declared)
        or _validate_exact_name(source_entity, declared)
    )


def _checked_declaration(
    source_entity: Entity,
    declaration: DeclarationEntry,
    params_kwargs: dict[str, Any],
) -> _Declared | _Problem:
    """The normalised parameters of the declaration, or its first problem.

    The parameters are read only once the marker is known to sit on a class
    or method body, as they always were.
    """
    problem = _validate_placement(source_entity, declaration)
    if problem is not None:
        return problem
    declared = _Declared.parse(params_kwargs)
    return _validate_declared(source_entity, declared) or declared


def _reject(
    source_entity: Entity,
    declaration: DeclarationEntry,
    problem: _Problem,
    rule_id_suffix: str,
) -> Tuple[List[Any], List[Evidence], List[Any]]:
    """Drop the declaration: a sentinel rule that fails at evaluation time and
    the compiler evidence of the problem."""
    if problem.issue == _INVALID_TARGET_ISSUE:
        evidence = invalid_target_evidence(
            source_entity,
            declaration,
            decorator="does_not_have",
            expected_kind="class_or_method",
            key="declaration",
        )
    else:
        evidence = _invalid_declaration(
            source_entity, declaration, issue=problem.issue, **problem.payload
        )
    sentinel = build_invalid_param_sentinel_rule(
        source_entity,
        decorator_name="does_not_have",
        rule_id_prefix=_SENTINEL_RULE_ID_PREFIX,
        rule_id_suffix=rule_id_suffix,
        **problem.invalid.fields(),
    )
    return [sentinel], [evidence], []


def _rule_params(
    source_entity: Entity, declared: _Declared, params_kwargs: dict[str, Any]
) -> dict[str, Any]:
    """The rule's parameters: the v1 ones, plus the v2 ones when a v2
    parameter is declared or the marker sits on a method body."""
    on_method = source_entity.kind == "method"
    rule_params: dict[str, Any] = {
        "name": _member_name(source_entity, declared),
        "member_kind": declared.member_kind,
        "storage": declared.storage,
        "declared_only": bool(params_kwargs.get("declared_only", False)),
        "fail_on_unmatched": False,
    }
    if not (_V2_PARAM_KEYS & set(params_kwargs) or on_method):
        return rule_params
    pattern = declared.pattern
    rule_params.update(
        {
            "name_match": declared.name_match,
            "aliases": declared.aliases,
            "pattern": pattern.strip() if isinstance(pattern, str) else None,
            "signature_mode": declared.signature_mode,
            "include_descriptors": declared.include_descriptors,
            "include_dynamic_attributes": declared.include_dynamic_attributes,
        }
    )
    if on_method:
        rule_params["signature_anchor_entity_id"] = source_entity.canonical_id
    return rule_params


def _build_rule(
    source_entity: Entity,
    declared: _Declared,
    params_kwargs: dict[str, Any],
    rule_id_suffix: str,
) -> Any:
    """The ``member_absence`` rule of a valid declaration.

    It is always scoped to a class: on a method body it is anchored at the
    owning class and the method is the forbidden member.
    """
    from pythonarchtesting.core.models import Rule, RuleSelector

    rule_params = _rule_params(source_entity, declared, params_kwargs)
    rule_id = (
        "NEG001/does_not_have/v2"
        if "name_match" in rule_params
        else "NEG001/does_not_have/v1"
    )
    if source_entity.kind == "method":
        selector_source_entity_id = _owning_class_id(source_entity) or ""
    else:
        selector_source_entity_id = source_entity.canonical_id
    return Rule(
        rule_id=with_rule_id_suffix(rule_id, rule_id_suffix),
        rule_type="member_absence",
        name="does_not_have",
        severity=marker_severity(params_kwargs),
        scope="class",
        evidence_type="static",
        selector=RuleSelector(
            source_entity_id=selector_source_entity_id,
            explicit_target=None,
        ),
        params=rule_params,
        message_template=(
            "Forbidden member present on {target.module_path}:{target.qualname}: "
            "{details.reason}"
        ),
        fix_hints=(
            "Remove the forbidden member or rename it.",
            (
                "If the member must exist, move the rule to a narrower target "
                "or adjust the member kind."
            ),
        ),
        enabled=True,
    )


def compile_does_not_have(
    source_entity: Entity,
    declaration: DeclarationEntry,
    cfg: Config,
    *,
    rule_id_suffix: str = "",
) -> Tuple[List[Any], List[Any], List[Any]]:
    """Compile a ``does_not_have`` declaration into a ``member_absence`` rule.

    The declaration is checked parameter by parameter in a fixed order; at
    the first problem it is dropped, and a sentinel rule plus one piece of
    compiler evidence report that problem instead.
    """
    _ = cfg
    params_kwargs = dict(declaration.params)
    checked = _checked_declaration(source_entity, declaration, params_kwargs)
    if isinstance(checked, _Problem):
        return _reject(source_entity, declaration, checked, rule_id_suffix)
    return [_build_rule(source_entity, checked, params_kwargs, rule_id_suffix)], [], []


__all__ = ["compile_does_not_have"]
