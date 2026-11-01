"""Evaluators for ``module_interface``: a module used only through its interface.

The interface is the names the marker lists, or, without names, the
module's public names (no leading underscore; dunder names count as public).
Names given for the reference are translated to the target's through the
matching, so a renamed entity is still judged as the reference's; the
module itself is the one the matching paired with the reference's (a renamed
module needs an assisted-pairing mapping).

The static rule reads every other module of the target: ``from module import
name`` and ``alias.name`` on a name bound to the module. The runtime rule
looks at the calls other modules make into the module while the entry runs.
"""

from __future__ import annotations

import ast
from typing import Any, Iterator

from pythonarchtesting.core.models import EvalContext, Rule, RuleResult
from pythonarchtesting.dynamic.translation import NameTranslation
from pythonarchtesting.entities import Entity
from pythonarchtesting.execution.import_edges import (
    _is_type_checking_test,
    _resolve_relative_module,
    collect_canonical_module_entities,
)
from pythonarchtesting.matching import MatchResult

from .messages import _build_rule_result
from .runtime_structure import _coverage, _coverage_note, _describe_call, run_edges

_MAX_REPORTED = 25


def _public(name: str) -> bool:
    return not name.startswith("_") or (name.startswith("__") and name.endswith("__"))


def _allowed(rule: Rule, names: NameTranslation) -> set[str] | None:
    """The target's names of the interface, or ``None`` for "the public names"."""
    listed = list(rule.params.get("names") or [])
    if not listed:
        return None
    module = str(rule.params.get("module", ""))
    allowed = set(listed)
    for name in listed:
        found = names.target_name(module, name)
        if found is not None:
            allowed.add(found[1].split(".")[0])
    return allowed


def _permits(name: str, allowed: set[str] | None) -> bool:
    return _public(name) if allowed is None else name in allowed


def _type_checking_lines(tree: ast.AST) -> set[int]:
    lines: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.If) and _is_type_checking_test(node.test):
            for child in node.body:
                for inner in ast.walk(child):
                    if hasattr(inner, "lineno"):
                        lines.add(int(inner.lineno))
    return lines


def _own_name(name: str, package: str | tuple[str | None, ...] | None) -> str:
    """An absolute import name without the project's package prefix.

    ``package`` is the name the project is imported under, or several (a
    submission may import itself under the reference's name); the package
    itself is ``""``.
    """
    names = (package,) if isinstance(package, str) or package is None else package
    for prefix in filter(None, names):
        if name == prefix:
            return ""
        if name.startswith(f"{prefix}."):
            return name[len(prefix) + 1 :]
    return name


def _chain(node: ast.AST) -> list[str] | None:
    """``a.b.c`` as ``["a", "b", "c"]``; ``None`` for anything else."""
    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if not isinstance(node, ast.Name):
        return None
    return [node.id, *reversed(parts)]


def _uses(
    entity: Entity,
    module: str,
    skip_type_checking: bool,
    package: str | tuple[str | None, ...] | None = None,
) -> Iterator[tuple[str, int, str]]:
    """``(name, line, how)`` for every use of ``module``'s names in ``entity``.

    ``from module import name`` uses ``name``; a name bound to the module
    itself (``from pkg import module``, ``import pkg.module as m``,
    ``import pkg.module``) uses whatever is reached through it
    (``m.name``, ``pkg.module.name``). ``package`` is the name the project is
    imported under, for absolute imports through it.
    """
    tree = entity.extras.get("ast_node")
    if tree is None:
        return
    hidden = _type_checking_lines(tree) if skip_type_checking else set()
    # How the code spells the module: a chain of names, e.g. ["m"] or
    # ["pkg", "models"].
    spellings: set[tuple[str, ...]] = set()
    parent, _, last = module.rpartition(".")
    for node in ast.walk(tree):
        if getattr(node, "lineno", None) in hidden:
            continue
        if isinstance(node, ast.ImportFrom):
            base = (
                _resolve_relative_module(
                    importer_module=entity.module_path,
                    filepath_rel=entity.filepath_rel,
                    level=node.level,
                    module=node.module,
                )
                if node.level
                else _own_name(node.module or "", package)
            )
            for alias in node.names:
                if base == module and alias.name != "*":
                    how = f"from {module or '__init__'} import {alias.name}"
                    yield alias.name, node.lineno, how
                elif base == parent and alias.name == last:
                    spellings.add((alias.asname or alias.name,))
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if _own_name(alias.name, package) != module:
                    continue
                if alias.asname:
                    spellings.add((alias.asname,))
                else:
                    spellings.add(tuple(alias.name.split(".")))
    if not spellings:
        return
    for node in ast.walk(tree):
        if not isinstance(node, ast.Attribute) or node.lineno in hidden:
            continue
        chain = _chain(node.value)
        if chain is not None and tuple(chain) in spellings:
            yield node.attr, node.lineno, f"{'.'.join(chain)}.{node.attr}"


class ModuleInterfaceEvaluator:
    """Static ``module_interface``: imports of the module's names by other modules."""

    def evaluate(
        self,
        rule: Rule,
        source: Entity,
        target: Entity,
        match: MatchResult,
        ctx: EvalContext,
    ) -> RuleResult:
        names = NameTranslation.from_context(ctx)
        allowed = _allowed(rule, names)
        module = str(target.module_path)
        skip = bool(rule.params.get("ignore_type_checking", True))
        violations: list[str] = []
        for entity in collect_canonical_module_entities(
            entities=ctx.target_index.all_sorted
        ):
            if entity.module_path == module:
                continue
            for name, line, how in _uses(
                entity,
                module,
                skip,
                (
                    getattr(ctx, "target_package", None),
                    getattr(ctx, "source_package", None),
                ),
            ):
                if not _permits(name, allowed):
                    violations.append(
                        f"{how} uses {name}, which is not in the interface of "
                        f"{module or '__init__'} ({entity.filepath_rel}:{line})"
                    )
        details: dict[str, Any] = {
            "reason": "",
            "summary": "",
            "module": module,
            "interface": sorted(allowed) if allowed is not None else "public names",
        }
        return _finish(rule, source, target, match, details, violations, module)


def _finish(
    rule: Rule,
    source: Entity,
    target: Entity,
    match: MatchResult,
    details: dict[str, Any],
    violations: list[str],
    module: str,
) -> RuleResult:
    if violations:
        details["violations"] = violations[:_MAX_REPORTED]
        details["violation_count"] = len(violations)
        details["reason"] = "violation"
        more = f" (+{len(violations) - 1} more)" if len(violations) > 1 else ""
        details["summary"] = violations[0] + more
        return _build_rule_result(rule, source, target, match, "FAILED", details, ())
    details["reason"] = "no_violations"
    details["summary"] = details.get("summary") or (
        f"other modules use {module or '__init__'} only through its interface"
    )
    return _build_rule_result(rule, source, target, match, "OK", details, ())


class RuntimeModuleInterfaceEvaluator:
    """Runtime ``module_interface``: calls other modules make into the module."""

    def evaluate(
        self,
        rule: Rule,
        source: Entity,
        target: Entity,
        match: MatchResult,
        ctx: EvalContext,
    ) -> RuleResult:
        cases = list(rule.params.get("cases") or [])
        details: dict[str, Any] = {
            "reason": "",
            "summary": "",
            "case_count": len(cases),
            "entry": rule.params.get("entry"),
        }
        observed = run_edges(rule, source, target, ctx, details)
        if isinstance(observed, str):
            return _build_rule_result(
                rule, source, target, match, observed, details, ()
            )
        _, target_cases, names = observed
        module = str(rule.params.get("module", ""))
        listed = set(rule.params.get("names") or [])
        violations: list[str] = []
        seen: set[tuple[str, str]] = set()
        for case in target_cases:
            for call in case.get("calls") or []:
                callee = str(call.get("callee"))
                into = names.source_module(str(call.get("module")), callee)
                origin = names.source_module(
                    str(call.get("from")), str(call.get("caller"))
                )
                if into != (module or "__init__") or origin == (module or "__init__"):
                    continue
                top = callee.split(".")[0]
                found = names.source_name(str(call.get("module")), top)
                name = found[1] if found is not None else top
                if "." in callee and _public(name):
                    # A method of a public class: the object may have come
                    # out through the interface (a function returning it).
                    continue
                permitted = name in listed if listed else _public(name)
                if permitted or (origin, name) in seen:
                    continue
                seen.add((origin, name))
                violations.append(
                    f"case {case.get('index')}: {origin} calls {name} of {module or '__init__'}, "
                    f"which is not in its interface ({_describe_call(call)})"
                )
        coverage = _coverage(target_cases)
        if coverage is not None:
            details["coverage"] = coverage
        details["summary"] = (
            f"{len(cases)} case(s) called {module} only through its interface"
            + _coverage_note(coverage)
        )
        return _finish(rule, source, target, match, details, violations, module)


__all__ = ["ModuleInterfaceEvaluator", "RuntimeModuleInterfaceEvaluator"]
