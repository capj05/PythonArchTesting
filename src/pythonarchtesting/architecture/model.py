"""The reference's architecture as data (F4.1): what ``architecture_entry`` compares with.

``describe`` reads the reference and returns its model: the modules, the
imports between them (with the line that makes each), the libraries each
module imports, the ``architecture_entry`` declaration, and, when asked and
declared with ``entry`` and ``cases``, what the reference does at run time:
the calls between modules, which module creates objects of which class, and
the libraries it calls. Edges are named as the comparison names them (the
package itself is ``__init__``), so a client can quote them in exceptions
(``allow=["a -> b"]``) and in feedback.

It only describes; nothing is judged. The CLI writes it with
``--write-model``, the MCP server returns it from ``describe_architecture``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable, Mapping

from pythonarchtesting.architecture.compare import DEFAULT_IGNORE_EXTERNAL
from pythonarchtesting.execution.module_structure import Edge

MODEL_VERSION = 1
# The markers' own package: importing it declares, it is no technology.
_MARKERS = "pythonarchtesting"
MODES = ("static", "full")
_STATIC_RULE = "DEP004/architecture_entry/v1"
_RUNTIME_RULE = "DYN011/architecture_entry/v1"
_DECLARED = (
    "policy",
    "allow",
    "forbid",
    "ignore_external",
    "ignore_type_checking",
)


def _rule(rules: Iterable[Any], rule_id: str) -> Any | None:
    return next((r for r in rules if str(r.rule_id) == rule_id), None)


def _edge(edge: Edge) -> str:
    return f"{edge[0]} -> {edge[1]}"


def _declaration(static: Any | None, runtime: Any | None) -> dict[str, Any]:
    if static is None:
        return {
            "declared": False,
            "policy": "allow_new_modules",
            "allow": [],
            "forbid": [],
            "ignore_external": list(DEFAULT_IGNORE_EXTERNAL),
            "ignore_type_checking": True,
        }
    params = static.params
    found: dict[str, Any] = {"declared": True}
    for name in _DECLARED:
        if name in params:
            value = params[name]
            found[name] = list(value) if isinstance(value, (list, tuple)) else value
    found.setdefault("policy", "allow_new_modules")
    found.setdefault("ignore_external", list(DEFAULT_IGNORE_EXTERNAL))
    if runtime is not None:
        found["entry"] = runtime.params.get("entry")
        found["case_count"] = len(runtime.params.get("cases") or [])
        found["require_all"] = bool(runtime.params.get("require_all", False))
    return found


def _ignored(name: str, ignore: Iterable[str]) -> bool:
    return any(name == item or name.startswith(f"{item}.") for item in ignore)


def describe_static(
    entities: list[Any], package: str | None, rules: Iterable[Any]
) -> dict[str, Any]:
    """The reference's modules, imports and libraries, and its declaration."""
    from pythonarchtesting.execution.evaluators.architecture import (
        module_name,
        static_import_edges,
    )
    from pythonarchtesting.execution.import_edges import (
        collect_canonical_module_entities,
    )

    rules = list(rules)
    static, runtime = _rule(rules, _STATIC_RULE), _rule(rules, _RUNTIME_RULE)
    declaration = _declaration(static, runtime)
    ignore_tc = bool(declaration.get("ignore_type_checking", True))
    graph, libraries, _ = static_import_edges(entities, ignore_tc, package)
    modules = sorted(
        (
            {"name": module_name(e.module_path), "file": str(e.filepath_rel)}
            for e in collect_canonical_module_entities(entities=entities)
        ),
        key=lambda item: item["name"],
    )
    imports = sorted(
        (
            {
                "edge": _edge((module_name(a), module_name(b))),
                "at": f"{edge.filepath_rel}:{edge.lineno}",
            }
            for (a, b), edge in graph.items()
        ),
        key=lambda item: item["edge"],
    )
    ignore = list(declaration.get("ignore_external") or [])
    external = sorted(
        (
            {
                "edge": _edge((module_name(module), library)),
                "at": f"{edge.filepath_rel}:{edge.lineno}",
            }
            for (module, library), edge in libraries.items()
            if not _ignored(library, ignore) and library != _MARKERS
        ),
        key=lambda item: item["edge"],
    )
    return {
        "version": MODEL_VERSION,
        "package": package,
        "modules": modules,
        "declaration": declaration,
        "static": {"imports": imports, "external": external},
    }


def describe_runtime(
    outcome: Any,
    ignore: Iterable[str] = DEFAULT_IGNORE_EXTERNAL,
    imported: Iterable[str] = (),
) -> dict[str, Any]:
    """What the reference's cases did: calls, objects created, libraries called.

    ``status`` is ``completed`` only when every case ran: the comparison ends
    in ``ERROR`` (``reference_failed``) as soon as one did not, and judges
    nothing. ``libraries_compared`` is what a target may call: the libraries
    the cases called and every one the reference imports (``imported``).
    """
    from pythonarchtesting.execution.evaluators.architecture import (
        case_calls,
        case_instances,
    )
    from pythonarchtesting.execution.evaluators.runtime_structure import case_coverage

    calls: dict[Edge, Mapping[str, Any]] = {}
    libraries: dict[Edge, Mapping[str, Any]] = {}
    instances: dict[Edge, Mapping[str, Any]] = {}
    cases = list(outcome.cases)
    for case in cases:
        internal, outward = case_calls(case, None)
        for pair, call in internal.items():
            calls.setdefault(pair, call)
        for pair, call in outward.items():
            libraries.setdefault(pair, call)
        named, _ = case_instances(case, None)
        for pair, item in named.items():
            instances.setdefault(pair, item)
    ignore = list(ignore)
    broken = [case for case in cases if case.get("status") == "error"]
    status = outcome.status
    if status == "completed" and broken:
        status = "reference_failed"
    found: dict[str, Any] = {
        "status": status,
        "cases": [
            {
                "index": case.get("index"),
                "status": case.get("status"),
                **({"failures": case["failures"]} if case.get("failures") else {}),
            }
            for case in cases
        ],
        "calls": sorted(_edge(edge) for edge in calls),
        "instances": sorted(_edge(edge) for edge in instances),
        "external": sorted(
            _edge(edge) for edge in libraries if not _ignored(edge[1], ignore)
        ),
        "libraries_compared": sorted(
            {
                name
                for name in {package for _, package in libraries} | set(imported)
                if not _ignored(name, ignore) and name != _MARKERS
            }
        ),
    }
    coverage = case_coverage(cases)
    if coverage is not None:
        found["coverage"] = coverage
    if outcome.status != "completed" and getattr(outcome, "error", None):
        found["error"] = outcome.error
    elif broken:
        first = broken[0]
        reason = (first.get("failures") or ["no detail"])[0]
        found["error"] = f"case {first.get('index')}: {reason}"
    return found


def _declared(entities: Iterable[Any]) -> bool:
    """Whether any entity declares ``architecture_entry``, valid or not."""
    from pythonarchtesting.rules.compilation.declarations import (
        normalize_declaration_entries,
    )

    return any(
        declaration.kind == "architecture_entry"
        for entity in entities
        for declaration in normalize_declaration_entries(entity)
    )


def _compared(
    rules: list[Any], entities: list[Any], problems: list[str]
) -> dict[str, str]:
    """When the comparison runs on this reference, as the rule compiler decides."""
    if _rule(rules, _STATIC_RULE) is not None:
        runtime = _rule(rules, _RUNTIME_RULE) is not None
        return {"static": "always", "runtime": "with --dynamic" if runtime else "never"}
    is_package = any(e.kind == "module" and not e.module_path for e in entities)
    if problems or _declared(entities) or not is_package:
        # A declaration that does not compile turns --architecture off too.
        return {"static": "never", "runtime": "never"}
    return {"static": "with --architecture", "runtime": "never"}


def describe(
    state: Any,
    *,
    mode: str = "static",
    source_root: Any = None,
    sandbox: Any = None,
) -> dict[str, Any]:
    """The model of a prepared reference (``prepare_source``'s state).

    ``compared`` says when a target is compared with it at all. A declaration
    that does not compile is ``declared`` with its ``problems`` and nothing
    else: no rule exists, so no setting applies. ``mode="full"`` also runs the
    declared cases on the reference (from ``source_root``, the reference's
    directory by default, sandboxed by ``sandbox``); without a declaration
    that has ``entry`` and ``cases``, ``runtime.reason`` says why not.
    """
    if mode not in MODES:
        raise ValueError(f"mode must be one of {', '.join(MODES)}: {mode}")
    entities = list(state.source_by_id.values())
    rules = list(state.rules)
    root = Path(str(state.source_path)).resolve() if state.source_path else None
    # The name the project is imported under, as the evaluation takes it.
    package = root.name if root is not None else None
    model = describe_static(entities, package, rules)
    problems = [
        f"{r.params.get('param')}: {r.params.get('compiler_reason')}"
        for r in rules
        if str(r.rule_id).startswith("DEP004/architecture_entry/invalid")
    ]
    if problems:
        model["declaration"] = {"declared": True, "problems": problems}
    model["compared"] = _compared(rules, entities, problems)
    if mode == "static":
        return model
    runtime_rule = _rule(rules, _RUNTIME_RULE)
    if runtime_rule is None:
        reason = (
            "the architecture_entry declaration does not compile: "
            + "; ".join(problems)
            if problems
            else "the reference declares no architecture_entry with entry and cases"
        )
        model["runtime"] = {"status": "not_run", "reason": reason}
        return model
    run_root = source_root if source_root is not None else root
    if run_root is None:
        raise ValueError("mode='full' needs the reference's directory (source_root)")
    entity = state.source_by_id.get(runtime_rule.selector.source_entity_id)
    from pythonarchtesting.dynamic.runner import run_cases
    from pythonarchtesting.execution.evaluators.architecture import OBSERVE

    outcome = run_cases(
        target_root=Path(run_root),
        module_path=entity.module_path,
        qualname=entity.qualname,
        kind=entity.kind,
        cases=list(runtime_rule.params.get("cases") or []),
        init=runtime_rule.params.get("init"),
        timeout_s=float(runtime_rule.params.get("timeout_s", 5.0)),
        sandbox=sandbox,
        observe=OBSERVE,
    )
    model["runtime"] = describe_runtime(
        outcome,
        model["declaration"].get("ignore_external") or (),
        imported=[
            item["edge"].split(" -> ")[1] for item in model["static"]["external"]
        ],
    )
    return model


__all__ = ["MODES", "MODEL_VERSION", "describe", "describe_runtime", "describe_static"]
