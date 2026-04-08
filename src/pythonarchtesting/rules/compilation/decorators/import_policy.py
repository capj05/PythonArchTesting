from __future__ import annotations

from typing import Any, List, Literal, Tuple, cast

from pythonarchtesting.config import Config
from pythonarchtesting.entities import DeclarationEntry, Entity

from ..common import with_rule_id_suffix


def compile_forbid_imports(
    source_entity: Entity,
    declaration: DeclarationEntry,
    cfg: Config,
    *,
    rule_id_suffix: str = "",
) -> Tuple[List[Any], List[Any], List[Any]]:
    """Compile forbidden imports policy rules from annotation declarations."""
    from pythonarchtesting.core.models import Rule, RuleSelector

    _ = cfg
    params_kwargs = dict(declaration.params)

    forbidden_raw = params_kwargs.get("forbidden", [])
    if isinstance(forbidden_raw, str):
        forbidden = [forbidden_raw]
    elif isinstance(forbidden_raw, list):
        forbidden = [str(item) for item in forbidden_raw if isinstance(item, str)]
    else:
        forbidden = []

    allow_raw = params_kwargs.get("allow", [])
    if isinstance(allow_raw, str):
        allow = [allow_raw]
    elif isinstance(allow_raw, list):
        allow = [str(item) for item in allow_raw if isinstance(item, str)]
    else:
        allow = []

    ignore_globs_raw = params_kwargs.get("ignore_globs", [])
    if isinstance(ignore_globs_raw, str):
        ignore_globs = [ignore_globs_raw]
    elif isinstance(ignore_globs_raw, list):
        ignore_globs = [str(item) for item in ignore_globs_raw if isinstance(item, str)]
    else:
        ignore_globs = []

    scope = str(params_kwargs.get("scope", "package")).lower()
    if scope not in {"package", "entity"}:
        scope = "package"

    package = params_kwargs.get("package")
    if package is not None and not isinstance(package, str):
        package = None

    ignore_type_checking = bool(params_kwargs.get("ignore_type_checking", True))

    base_severity_raw = str(params_kwargs.get("severity", "error")).lower()
    if base_severity_raw in {"error", "warning", "info"}:
        base_severity = cast(Literal["error", "warning", "info"], base_severity_raw)
    else:
        base_severity = "error"

    selector = RuleSelector(
        source_entity_id=source_entity.canonical_id,
        explicit_target=None,
    )

    rule = Rule(
        rule_id=with_rule_id_suffix("DEP001/forbid_imports/v1", rule_id_suffix),
        rule_type="import_policy",
        name="forbid_imports",
        severity=base_severity,
        scope=source_entity.kind,
        evidence_type="static",
        selector=selector,
        params={
            "forbidden": sorted(set(forbidden)),
            "scope": scope,
            "package": package,
            "ignore_type_checking": ignore_type_checking,
            "allow": sorted(set(allow)),
            "ignore_globs": sorted(set(ignore_globs)),
            "fail_on_unmatched": False,
        },
        message_template=(
            "DEP001 forbidden imports found in package "
            "'{details.package_prefix}': {details.forbidden_modules}"
        ),
        fix_hints=(
            "Remove or replace imports that violate the forbidden dependency policy.",
        ),
        enabled=True,
    )

    return [rule], [], []


__all__ = ["compile_forbid_imports"]
