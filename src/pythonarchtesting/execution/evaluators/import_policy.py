from __future__ import annotations

import ast
import fnmatch
from typing import Any, Dict, List

from pythonarchtesting.core.models import EvalContext, Rule, RuleResult, RuleStatus
from pythonarchtesting.entities import Entity
from pythonarchtesting.matching import MatchResult


def _resolve_relative_module(
    *,
    importer_module: str,
    filepath_rel: str,
    level: int,
    module: str | None,
) -> str:
    importer_parts = importer_module.split(".") if importer_module else []
    is_package_module = filepath_rel.endswith("/__init__.py")
    if is_package_module:
        context_parts = importer_parts
    else:
        context_parts = importer_parts[:-1]
    remove_parts = max(level - 1, 0)
    if remove_parts > len(context_parts):
        base_parts: List[str] = []
    else:
        base_parts = context_parts[: len(context_parts) - remove_parts]
    if module:
        base_parts.extend(part for part in module.split(".") if part)
    return ".".join(base_parts)


def _normalize_import_targets(
    *,
    kind: str,
    importer_module: str,
    filepath_rel: str,
    module: str,
    name: str | None,
) -> List[str]:
    if kind == "import":
        return [module] if module else []

    level = 0
    while level < len(module) and module[level] == ".":
        level += 1
    module_name = module[level:] if level > 0 else module
    base_module = (
        _resolve_relative_module(
            importer_module=importer_module,
            filepath_rel=filepath_rel,
            level=level,
            module=module_name if module_name else None,
        )
        if level > 0
        else module_name
    )
    targets: List[str] = []
    if base_module:
        targets.append(base_module)
    if name and name != "*" and base_module:
        targets.append(f"{base_module}.{name}")
    elif name and name != "*" and not base_module:
        targets.append(name)
    return targets


def _is_type_checking_test(test: ast.AST) -> bool:
    if isinstance(test, ast.Name):
        return test.id == "TYPE_CHECKING"
    if isinstance(test, ast.Attribute):
        return (
            isinstance(test.value, ast.Name)
            and test.value.id == "typing"
            and test.attr == "TYPE_CHECKING"
        )
    return False


def _collect_import_edges_from_node(
    node: ast.AST,
    *,
    module_path: str,
    filepath_rel: str,
    in_type_checking: bool = False,
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for child in ast.iter_child_nodes(node):
        child_in_type_checking = in_type_checking
        if isinstance(child, ast.If) and _is_type_checking_test(child.test):
            child_in_type_checking = True

        if isinstance(child, ast.Import):
            for alias in child.names:
                if not alias.name:
                    continue
                rows.append(
                    {
                        "kind": "import",
                        "module": alias.name,
                        "name": None,
                        "lineno": getattr(child, "lineno", 0),
                        "filepath": filepath_rel,
                        "module_path": module_path,
                        "in_type_checking": child_in_type_checking,
                    }
                )
        elif isinstance(child, ast.ImportFrom):
            prefix = "." * (getattr(child, "level", 0) or 0)
            mod = prefix + (child.module or "")
            for alias in child.names:
                rows.append(
                    {
                        "kind": "importfrom",
                        "module": mod,
                        "name": alias.name,
                        "lineno": getattr(child, "lineno", 0),
                        "filepath": filepath_rel,
                        "module_path": module_path,
                        "in_type_checking": child_in_type_checking,
                    }
                )

        rows.extend(
            _collect_import_edges_from_node(
                child,
                module_path=module_path,
                filepath_rel=filepath_rel,
                in_type_checking=child_in_type_checking,
            )
        )
    return rows


def _matches_prefix(name: str, prefixes: List[str]) -> str | None:
    for prefix in prefixes:
        if name == prefix or name.startswith(prefix + "."):
            return prefix
    return None


class ImportPolicyEvaluator:
    """Evaluator for forbidden import policy rules (DEP001)."""

    def evaluate(
        self,
        rule: Rule,
        source: Entity,
        target: Entity,
        match: MatchResult,
        ctx: EvalContext,
    ) -> RuleResult:
        forbidden = [str(item) for item in list(rule.params.get("forbidden", []))]
        allow = [str(item) for item in list(rule.params.get("allow", []))]
        ignore_globs = [str(item) for item in list(rule.params.get("ignore_globs", []))]
        ignore_type_checking = bool(rule.params.get("ignore_type_checking", True))
        scope = str(rule.params.get("scope", "package"))

        if scope == "entity":
            scope_modules = {target.module_path}
            package_prefix = target.module_path
        else:
            configured_package = rule.params.get("package")
            if isinstance(configured_package, str) and configured_package:
                package_prefix = configured_package
            else:
                package_prefix = (
                    source.module_path.split(".")[0] if source.module_path else ""
                )
            scope_modules = {
                entity.module_path
                for entity in ctx.target_index.all_sorted
                if entity.module_path == package_prefix
                or entity.module_path.startswith(package_prefix + ".")
            }

        imported_rows: List[Dict[str, Any]] = []
        for entity in ctx.target_index.all_sorted:
            if entity.module_path not in scope_modules:
                continue
            if ignore_globs and any(
                fnmatch.fnmatch(entity.filepath_rel, pattern)
                for pattern in ignore_globs
            ):
                continue
            node = entity.extras.get("ast_node")
            if node is None:
                continue
            imported_rows.extend(
                _collect_import_edges_from_node(
                    node,
                    module_path=entity.module_path,
                    filepath_rel=entity.filepath_rel,
                )
            )

        occurrences: List[Dict[str, Any]] = []
        found_forbidden: set[str] = set()

        for row in imported_rows:
            if ignore_type_checking and row.get("in_type_checking"):
                continue
            targets = _normalize_import_targets(
                kind=str(row.get("kind", "")),
                importer_module=str(row.get("module_path", "")),
                filepath_rel=str(row.get("filepath", "")),
                module=str(row.get("module", "")),
                name=row.get("name"),
            )
            for imported in targets:
                if _matches_prefix(imported, allow) is not None:
                    continue
                matched = _matches_prefix(imported, forbidden)
                if matched is None:
                    continue
                found_forbidden.add(matched)
                occurrences.append(
                    {
                        "filepath": row.get("filepath"),
                        "lineno": int(row.get("lineno", 0)),
                        "imported_module": imported,
                        "forbidden_prefix": matched,
                    }
                )

        occurrences = sorted(
            occurrences,
            key=lambda item: (
                str(item.get("filepath", "")),
                int(item.get("lineno", 0)),
                str(item.get("imported_module", "")),
            ),
        )
        forbidden_modules = sorted(found_forbidden)
        status: RuleStatus = "FAILED" if occurrences else "OK"
        details = {
            "package_prefix": package_prefix,
            "forbidden_modules": forbidden_modules,
            "occurrences": occurrences,
            "scope": scope,
            "match_status": match.status.value,
        }

        if status == "OK":
            return RuleResult(
                rule_id=rule.rule_id,
                status="OK",
                source_entity_id=source.canonical_id,
                target_entity_id=target.canonical_id,
                match_status=match.status.value,
                confidence=match.confidence,
                message="OK",
                evidence=(),
                details=details,
            )

        message = (
            f"DEP001 forbidden imports found in package '{package_prefix}': "
            f"{forbidden_modules}"
        )
        return RuleResult(
            rule_id=rule.rule_id,
            status="FAILED",
            source_entity_id=source.canonical_id,
            target_entity_id=target.canonical_id,
            match_status=match.status.value,
            confidence=match.confidence,
            message=message,
            evidence=(),
            details=details,
        )


__all__ = ["ImportPolicyEvaluator"]
