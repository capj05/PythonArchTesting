"""Evaluators for ``architecture_entry``: the target against the reference's model.

The static rule compares the import graphs of reference and target, and the
libraries each imports. Target modules are named by the reference modules
they were matched to, so a renamed module still stands for its original.
The comparison itself lives in ``pythonarchtesting.architecture.compare``;
this module collects the edges and turns the comparison into a result:
FAILED on a divergence, OK otherwise, with what the policy could not decide
listed in ``details.undecided`` for a person to judge.
"""

from __future__ import annotations

import dataclasses
from typing import Any, Callable, Mapping

from pythonarchtesting.architecture.compare import (
    EdgeDiff,
    class_module,
    compare_edges,
    compare_instances,
    compare_packages,
    fold_new_modules,
    forbidden,
    format_edge,
    parse_edge,
)
from pythonarchtesting.core.models import EvalContext, Rule, RuleResult
from pythonarchtesting.dynamic.translation import NameTranslation
from pythonarchtesting.entities import Entity
from pythonarchtesting.execution.import_edges import (
    NormalizedImportEdge,
    Packages,
    collect_canonical_module_entities,
    collect_import_references_from_node,
    is_own_import,
    normalize_import_reference,
    without_package,
)
from pythonarchtesting.execution.module_structure import (
    Edge,
    import_module_edges,
    module_of,
)
from pythonarchtesting.matching import MatchResult

from .messages import _build_rule_result
from .runtime_structure import _coverage, _coverage_note, _describe_call, run_edges

_MAX_REPORTED = 25
ROOT = "__init__"


def module_name(module: str) -> str:
    """The name a module goes by in the model: the package itself is ``__init__``."""
    return module or ROOT


def exceptions(rule: Rule, name: str) -> list[Edge]:
    return [parse_edge(item) for item in rule.params.get(name) or []]


def _import_edges(
    entities: list[Entity], ignore_type_checking: bool, package: Packages = None
) -> tuple[
    dict[Edge, NormalizedImportEdge], dict[Edge, NormalizedImportEdge], set[str]
]:
    """Internal module edges, ``(module, package)`` library edges, modules.

    An import from the project itself (relative, or through ``package``, the
    name the project is imported under) is never a library.
    """
    modules = collect_canonical_module_entities(entities=entities)
    internal = frozenset(entity.module_path for entity in modules)
    raw: list[NormalizedImportEdge] = []
    libraries: dict[Edge, NormalizedImportEdge] = {}
    for entity in modules:
        refs = collect_import_references_from_node(
            node=entity.extras["ast_node"],
            importer_module=entity.module_path,
            filepath_rel=entity.filepath_rel,
        )
        for ref in refs:
            own = is_own_import(ref, package)
            edges = normalize_import_reference(without_package(ref, package))
            raw.extend(edges)
            if own or (ignore_type_checking and ref.in_type_checking):
                continue
            for edge in edges:
                if not edge.imported_module or module_of(
                    edge.imported_module, internal
                ):
                    continue
                library = edge.imported_module.split(".")[0]
                if library:
                    libraries.setdefault((edge.importer_module, library), edge)
    graph = import_module_edges(
        _through_packages(raw, modules, internal),
        internal,
        ignore_type_checking=ignore_type_checking,
    )
    return graph, libraries, set(internal)


def _through_subpackages(reference: set[Edge], known: set[str]) -> set[Edge]:
    """``a -> pkg`` for every reference edge ``a -> pkg.module`` into a
    subpackage: importing the package whole (``from . import api``, then
    ``api.book()``) stands for importing the modules it re-exports."""
    packages = {
        module
        for module in known
        if module != ROOT and any(other.startswith(f"{module}.") for other in known)
    }
    return {
        (origin, package)
        for origin, end in reference
        for package in packages
        if end.startswith(f"{package}.") and origin != package
    }


def _through_packages(
    edges: list[NormalizedImportEdge], modules: list[Entity], internal: frozenset[str]
) -> list[NormalizedImportEdge]:
    """``from .pkg import Name`` as an import of the module ``pkg`` takes
    ``Name`` from, when ``pkg/__init__.py`` only re-exports it (a few hops)."""
    packages = {
        entity.module_path
        for entity in modules
        if str(entity.filepath_rel).endswith("__init__.py")
    }
    exported: dict[str, str] = {}
    for edge in edges:
        package = edge.importer_module
        if package not in packages or module_of(edge.imported_module, internal) in (
            None,
            package,
        ):
            continue  # not a package, or not a name from another own module
        name = edge.imported_module.rpartition(".")[2]
        exported.setdefault(
            f"{package}.{name}" if package else name, edge.imported_module
        )
    resolved = []
    for edge in edges:
        imported = edge.imported_module
        for _ in range(3):
            following = exported.get(imported)
            if (
                following is None
                or following == imported
                or edge.importer_module in packages
                and edge.importer_module == module_of(imported, internal)
            ):
                break
            imported = following
        resolved.append(
            edge
            if imported == edge.imported_module
            else dataclasses.replace(edge, imported_module=imported)
        )
    return resolved


def _rename(
    edges: Mapping[Edge, Any], origin: Callable[[str], str], end: Callable[[str], str]
) -> dict[Edge, Any]:
    renamed: dict[Edge, Any] = {}
    for (a, b), value in edges.items():
        pair = (origin(a), end(b))
        if pair[0] != pair[1]:
            renamed.setdefault(pair, value)
    return renamed


def finish_architecture(
    rule: Rule,
    source: Entity,
    target: Entity,
    match: MatchResult,
    details: dict[str, Any],
    diffs: dict[str, EdgeDiff],
    violations: list[str],
    passed: str,
) -> RuleResult:
    """The rule's result: FAILED on ``violations``, else OK, noting what is undecided."""
    details["policy"] = rule.params.get("policy", "allow_new_modules")
    divergences = list(details.get("divergences") or [])
    if len(divergences) > _MAX_REPORTED:
        details["divergences"] = divergences[:_MAX_REPORTED]
    if divergences:
        details["divergence_count"] = len(divergences)
    details["architecture"] = {name: diff.to_dict() for name, diff in diffs.items()}
    undecided = [
        f"{name}: {format_edge(edge)}"
        for name, diff in diffs.items()
        for edge in diff.undecided
    ]
    if undecided:
        details["undecided"] = undecided[:_MAX_REPORTED]
        details["undecided_count"] = len(undecided)
    if violations:
        details["violations"] = violations[:_MAX_REPORTED]
        details["violation_count"] = len(violations)
        details["reason"] = "violation"
        more = f" (+{len(violations) - 1} more)" if len(violations) > 1 else ""
        details["summary"] = violations[0] + more
        return _build_rule_result(rule, source, target, match, "FAILED", details, ())
    details["reason"] = "no_violations"
    note = (
        f"; {len(undecided)} undecided change(s) to review (details.undecided)"
        if undecided
        else ""
    )
    details["summary"] = passed + note
    return _build_rule_result(rule, source, target, match, "OK", details, ())


def _place(
    kind: str,
    layer: str,
    edge: Edge,
    *,
    file: str | None = None,
    module: str | None = None,
    line: int | None = None,
) -> dict[str, Any]:
    """A divergence a client can point at: the edge, and where the target makes it."""
    return {
        "kind": kind,
        "layer": layer,
        "edge": format_edge(edge),
        "file": file,
        "module": module,
        "line": line,
    }


def _import_place(
    layer: str, edge: Edge, found: NormalizedImportEdge | None
) -> dict[str, Any]:
    if found is None:
        return _place("divergent", layer, edge)
    return _place(
        "divergent",
        layer,
        edge,
        file=found.filepath_rel,
        module=module_name(found.importer_module),
        line=found.lineno,
    )


def _call_place(
    kind: str,
    layer: str,
    edge: Edge,
    call: dict[str, Any] | None,
    files: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Where the target makes ``edge``; for an absent edge, where the reference does."""
    if call is None:
        return _place(kind, layer, edge)
    module = str(call.get("from"))
    if kind == "absent":
        # The target does not make this call at all: no place in it to point
        # at. The reference's place says which step is missing.
        place = _place(kind, layer, edge)
        place["reference_module"] = module
        place["reference_line"] = call.get("line")
        return place
    file = call.get("file") or (files or {}).get(module)
    return _place(kind, layer, edge, file=file, module=module, line=call.get("line"))


def _target_files(entities: list[Entity]) -> dict[str, str]:
    """Module name as the probe reports it -> the target file that holds it."""
    return {
        module_name(str(entity.module_path)): str(entity.filepath_rel)
        for entity in entities
        if entity.kind == "module"
    }


def _line(edge: NormalizedImportEdge | None) -> str:
    return f"{edge.filepath_rel}:{edge.lineno}" if edge is not None else "?"


class ArchitectureStaticEvaluator:
    """Static ``architecture_entry``: the target's imports against the reference's."""

    def evaluate(
        self,
        rule: Rule,
        source: Entity,
        target: Entity,
        match: MatchResult,
        ctx: EvalContext,
    ) -> RuleResult:
        ignore_tc = bool(rule.params.get("ignore_type_checking", True))
        ref_graph, ref_libraries, ref_modules = _import_edges(
            list(ctx.source_by_id.values()), ignore_tc, ctx.source_package
        )
        target_graph, target_libraries, _ = _import_edges(
            list(ctx.target_index.all_sorted),
            ignore_tc,
            # A submission may import itself under the reference's name.
            (ctx.target_package, ctx.source_package),
        )
        names = NameTranslation.from_context(ctx)

        def translate(module: str) -> str:
            return module_name(names.source_module(module, ""))

        known = {module_name(module) for module in ref_modules}
        policy = str(rule.params.get("policy", "allow_new_modules"))
        renamed = _rename(target_graph, translate, translate)
        located = renamed if policy == "strict" else fold_new_modules(renamed, known)[0]
        # A subpackage's __init__ importing its own submodules re-exports
        # them: organisation inside a layer. The root package's re-exports
        # stay divergences (the owner's decision in F2).
        reexports = {
            pair: edge
            for pair, edge in renamed.items()
            if pair[0] != ROOT and pair[1].startswith(f"{pair[0]}.")
        }
        reference_imports = set(_rename(ref_graph, module_name, module_name))
        imports = compare_edges(
            reference_imports,
            {pair: edge for pair, edge in renamed.items() if pair not in reexports},
            policy=policy,
            known=known,
            allow=exceptions(rule, "allow"),
            forbid=exceptions(rule, "forbid"),
            permitted=_through_subpackages(reference_imports, known),
        )
        if reexports:
            imports = dataclasses.replace(
                imports, allowed=sorted(set(imports.allowed) | set(reexports))
            )
        libraries_target = _rename(target_libraries, translate, str)
        if policy != "strict":
            # A library a new helper module imports counts for its users.
            libraries_target = _fold_libraries(libraries_target, renamed, known)
        forbid = exceptions(rule, "forbid")
        external = compare_packages(
            {package for _, package in ref_libraries},
            libraries_target,
            ignore=list(rule.params.get("ignore_external") or []),
            allow=exceptions(rule, "allow"),
            forbid=exceptions(rule, "forbid"),
        )
        violations = [
            f"import {format_edge(edge)} "
            + (
                "is forbidden by the declaration"
                if forbidden(edge, forbid)
                else "is not in the reference"
            )
            + f" ({_line(located.get(edge))})"
            for edge in imports.divergent
        ] + [
            f"import of {edge[1]} in {edge[0]}: "
            + (
                "forbidden by the declaration"
                if forbidden(edge, forbid)
                else f"the reference uses no {edge[1]}"
            )
            + f" ({_line(libraries_target.get(edge))})"
            for edge in external.divergent
        ]
        details: dict[str, Any] = {
            "reason": "",
            "summary": "",
            "divergences": [
                _import_place("imports", edge, located.get(edge))
                for edge in imports.divergent
            ]
            + [
                _import_place("external", edge, libraries_target.get(edge))
                for edge in external.divergent
            ],
        }
        return finish_architecture(
            rule,
            source,
            target,
            match,
            details,
            {"imports": imports, "external": external},
            violations,
            f"imports follow the reference's {len(known)} module(s)",
        )


_OBSERVE = {"calls": "edges", "external": True, "instances": True}


def _calls(
    case: dict[str, Any], names: NameTranslation | None
) -> tuple[dict[Edge, dict[str, Any]], dict[Edge, dict[str, Any]]]:
    """A case's calls between modules and into libraries, in reference names."""
    internal: dict[Edge, dict[str, Any]] = {}
    libraries: dict[Edge, dict[str, Any]] = {}
    for call in case.get("calls") or []:
        origin = str(call.get("from"))
        if names is not None:
            origin = _reference_module(names, origin, str(call.get("caller")))
        if call.get("external"):
            libraries.setdefault((origin, str(call.get("module"))), call)
            continue
        end = str(call.get("module"))
        if names is not None:
            end = _reference_module(names, end, str(call.get("callee")))
        if origin != end:
            internal.setdefault((origin, end), call)
    return internal, libraries


def _reference_module(names: NameTranslation, module: str, qualname: str) -> str:
    """The reference module of code the probe saw in ``module``, as the model names it.

    The probe names the root package ``__init__``, entities know it as ``""``.
    """
    found = names.source_module("" if module == ROOT else module, qualname)
    return module_name(found)


def _creator(instance: dict[str, Any]) -> str:
    return str(instance.get("creator", "")).partition(":")[2]


def _instances(
    case: dict[str, Any], names: NameTranslation | None
) -> tuple[dict[Edge, dict[str, Any]], dict[Edge, dict[str, Any]]]:
    """Who created which object, in reference names, and what has no reference name."""
    named: dict[Edge, dict[str, Any]] = {}
    unnamed: dict[Edge, dict[str, Any]] = {}
    for instance in case.get("instances") or []:
        origin, module = str(instance.get("from")), str(instance.get("module"))
        cls = str(instance.get("class"))
        if names is None:
            named.setdefault((origin, f"{module}.{cls}"), instance)
            continue
        origin = _reference_module(names, origin, _creator(instance))
        # The probe names the root package "__init__"; entities know it as "".
        found = names.source_name("" if module == ROOT else module, cls)
        if found is None:
            unnamed.setdefault((origin, f"{module}.{cls}"), instance)
        else:
            named.setdefault((origin, f"{module_name(found[0])}.{found[1]}"), instance)
    return named, unnamed


def _fold_libraries(
    libraries: dict[Edge, Any], calls: Mapping[Edge, Any], known: set[str]
) -> dict[Edge, Any]:
    """A library a new helper module uses counts for the known modules using it."""
    folded: dict[Edge, Any] = {}
    for (origin, package), call in libraries.items():
        users = _users(origin, calls, known) if origin not in known else set()
        for user in users or {origin}:
            folded.setdefault((user, package), call)
    return folded


def _users(module: str, calls: Mapping[Edge, Any], known: set[str]) -> set[str]:
    """The known modules that reach ``module`` through modules the reference lacks."""
    found: set[str] = set()
    seen = {module}
    stack = [module]
    while stack:
        current = stack.pop()
        for origin, end in calls:
            if end != current or origin in seen:
                continue
            seen.add(origin)
            if origin in known:
                found.add(origin)
            else:
                stack.append(origin)
    return found


def _describe_instance(instance: dict[str, Any]) -> str:
    return f"{instance.get('file')}:{instance.get('line')}"


class ArchitectureRuntimeEvaluator:
    """Runtime ``architecture_entry``: what the target does against the reference.

    Both run the entry on the same cases. The calls between modules, the
    objects each module creates and the libraries called are compared, across
    all cases at once: a dependency counts if any case shows it.
    """

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
        observed = run_edges(rule, source, target, ctx, details, observe=_OBSERVE)
        if isinstance(observed, str):
            return _build_rule_result(
                rule, source, target, match, observed, details, ()
            )
        reference_cases, target_cases, names = observed
        policy = str(rule.params.get("policy", "allow_new_modules"))
        known = {module_name(e.module_path) for e in ctx.source_by_id.values()}
        allow, forbid = exceptions(rule, "allow"), exceptions(rule, "forbid")

        ref_calls: dict[Edge, Any] = {}
        ref_libraries: set[str] = set()
        ref_instances: dict[Edge, Any] = {}
        for case in reference_cases:
            internal, used = _calls(case, None)
            ref_calls.update({k: v for k, v in internal.items() if k not in ref_calls})
            ref_libraries |= {package for _, package in used}
            named, _ = _instances(case, None)
            ref_instances.update(named)
        static_graph, static_libraries, _ = _import_edges(
            list(ctx.source_by_id.values()),
            bool(rule.params.get("ignore_type_checking", True)),
            ctx.source_package,
        )
        # A call along an import the reference has is allowed even when the
        # reference's cases never made it: the import says the dependency is
        # intended, the cases only did not reach it.
        static_imports = set(_rename(static_graph, module_name, module_name))
        ref_libraries |= {package for _, package in static_libraries}

        calls: dict[Edge, Any] = {}
        libraries: dict[Edge, Any] = {}
        instances: dict[Edge, Any] = {}
        unnamed: dict[Edge, Any] = {}
        for case in target_cases:
            internal, outward = _calls(case, names)
            for pair, call in internal.items():
                calls.setdefault(pair, call)
            for pair, call in outward.items():
                libraries.setdefault(pair, call)
            named, other = _instances(case, names)
            for pair, item in named.items():
                instances.setdefault(pair, item)
            for pair, item in other.items():
                unnamed.setdefault(pair, item)

        folded_instances: dict[Edge, Any] = {}
        unplaced: list[Edge] = []
        for (origin, cls), item in instances.items():
            if origin in known or policy == "strict":
                folded_instances.setdefault((origin, cls), item)
                continue
            users = _users(origin, calls, known)
            if not users:
                unplaced.append((origin, cls))
            for user in users:
                folded_instances.setdefault((user, cls), item)

        call_diff = compare_edges(
            set(ref_calls),
            calls,
            policy=policy,
            known=known,
            allow=allow,
            forbid=forbid,
            permitted=static_imports,
        )
        instance_diff = compare_instances(
            set(ref_instances),
            folded_instances,
            policy=policy,
            reference_calls=set(ref_calls),
            allow=allow,
            forbid=forbid,
            modules=known,
        )
        instance_diff = EdgeDiff(
            convergent=instance_diff.convergent,
            divergent=instance_diff.divergent,
            absent=instance_diff.absent,
            undecided=sorted(
                set(instance_diff.undecided) | set(unnamed) | set(unplaced)
            ),
            allowed=instance_diff.allowed,
            reference=instance_diff.reference,
        )
        if policy != "strict":
            libraries = _fold_libraries(libraries, calls, known)
        library_diff = compare_packages(
            ref_libraries,
            libraries,
            ignore=list(rule.params.get("ignore_external") or []),
            allow=allow,
            forbid=forbid,
        )

        located = calls if policy == "strict" else fold_new_modules(calls, known)[0]
        violations = (
            [
                f"call {format_edge(edge)} "
                + (
                    "is forbidden by the declaration"
                    if forbidden(edge, forbid)
                    else "is not in the reference"
                )
                + f" ({_describe_call(located[edge]) if edge in located else '?'})"
                for edge in call_diff.divergent
            ]
            + [
                f"{edge[0]} creates {edge[1]}, "
                + (
                    "which the declaration forbids"
                    if edge in forbid
                    or forbidden((edge[0], class_module(edge[1], known)), forbid)
                    else f"which the reference's {edge[0]} never does"
                )
                + f" ({_describe_instance(folded_instances[edge])})"
                for edge in instance_diff.divergent
            ]
            + [
                f"{edge[0]} calls {edge[1]}, "
                + (
                    "which the declaration forbids"
                    if forbidden(edge, forbid)
                    else "which the reference never uses"
                )
                + f" ({_describe_call(libraries[edge])})"
                for edge in library_diff.divergent
            ]
        )
        if rule.params.get("require_all"):
            # A step the target skips: the reference's call never happened.
            violations += [
                f"the reference's call {format_edge(edge)} never happened "
                f"({_describe_call(ref_calls[edge])} in the reference)"
                for edge in call_diff.absent
            ]
        files = _target_files(list(ctx.target_index.all_sorted))
        details["divergences"] = (
            [
                _call_place("divergent", "calls", edge, located.get(edge), files)
                for edge in call_diff.divergent
            ]
            + [
                _call_place(
                    "divergent", "instances", edge, folded_instances[edge], files
                )
                for edge in instance_diff.divergent
            ]
            + [
                _call_place("divergent", "external", edge, libraries[edge], files)
                for edge in library_diff.divergent
            ]
            + (
                [
                    _call_place("absent", "calls", edge, ref_calls.get(edge))
                    for edge in call_diff.absent
                ]
                if rule.params.get("require_all")
                else []
            )
        )
        coverage = _coverage(target_cases)
        if coverage is not None:
            details["coverage"] = coverage
        return finish_architecture(
            rule,
            source,
            target,
            match,
            details,
            {"calls": call_diff, "instances": instance_diff, "external": library_diff},
            violations,
            f"{len(cases)} case(s) used only the reference's dependencies"
            + _coverage_note(coverage),
        )


__all__ = [
    "ArchitectureRuntimeEvaluator",
    "ArchitectureStaticEvaluator",
    "exceptions",
    "finish_architecture",
    "module_name",
]
