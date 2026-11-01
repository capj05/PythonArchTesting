"""The architecture section of a target's Markdown page (F3.1).

``architecture_entry`` compares the target with the reference's module
dependencies and leaves the comparison in ``details.architecture`` of its
results, one diff per layer of the model (imports, calls, instances,
libraries). This section shows those diffs: per rule a count table, then the
edges that matter to a reader, the divergent ones (violations), the undecided
ones (for a person to judge) and the absent ones. Convergent edges are only
counted; they are what the reference expects.
"""

from __future__ import annotations

from typing import Any, Iterable, List, Mapping, Sequence

from pythonarchtesting.architecture.views import (
    INTERNAL_LAYERS,
    REFERENCE,
    RUNTIME_LAYERS,
    STATIC_LAYERS,
    TARGET_KINDS,
    ModuleMetrics,
    aggregate,
    architectures,
    layers_edges,
    matrix,
    metrics,
    static_runtime,
)

from .escape import escape_markdown
from .table import Table, render_markdown_table

_KINDS = ("convergent", "divergent", "absent", "undecided", "allowed")
_LISTED = (
    ("divergent", "Divergent (violations)"),
    ("undecided", "Undecided (to review)"),
    ("absent", "Absent"),
    ("allowed", "Allowed by an exception"),
)
_MAX_LISTED = 20
_MAX_MATRIX = 15
_KIND_NAMES = {"DEP": "Static", "DYN": "Runtime"}
# An edge this share of a run's targets diverge on (or lack) points at the
# model rather than at each solution; judged from this many targets up.
_MODEL_SUSPECT_SHARE = 0.9
_MODEL_SUSPECT_TARGETS = 3
# An undecided edge everyone shares is what the policy leaves open, not a
# defect of the model.
_MODEL_SUSPECT_KINDS = ("divergent", "absent")


def _architecture(result: Any) -> dict[str, Any] | None:
    details = getattr(result, "details", None) or {}
    architecture = details.get("architecture") if isinstance(details, dict) else None
    return architecture if isinstance(architecture, dict) and architecture else None


def _rule_name(code: str) -> str:
    return f"{_KIND_NAMES.get(code[:3], 'Rule')} ({escape_markdown(code)})"


def _heading(result: Any) -> str:
    code = str(result.rule_id).split("/")[0]
    return f"### {_rule_name(code)}: {escape_markdown(str(result.status))}"


def _capped(items: List[str]) -> List[str]:
    if len(items) > _MAX_LISTED:
        more = len(items) - _MAX_LISTED
        return items[:_MAX_LISTED] + [f"(+{more} more)"]
    return items


def _edges(layer: str, edges: Sequence[str]) -> List[str]:
    return [f"{escape_markdown(layer)} `{edge}`" for edge in edges]


def _listed(architecture: dict[str, Any], kind: str) -> List[str]:
    items: List[str] = []
    for layer, diff in architecture.items():
        items.extend(_edges(layer, list((diff or {}).get(kind) or [])))
    return _capped(items)


def _matrix_lines(architecture: Mapping[str, Any]) -> List[str]:
    lines: List[str] = []
    for layer in INTERNAL_LAYERS:
        if layer not in architecture:
            continue
        found = matrix(architecture[layer], layer, architecture)
        if not found.modules:
            continue
        if len(found.modules) > _MAX_MATRIX:
            lines.extend(
                [
                    f"- Dependency matrix of {escape_markdown(layer)} left out: "
                    f"{len(found.modules)} modules (more than {_MAX_MATRIX})",
                    "",
                ]
            )
            continue
        rows = tuple(
            (
                _module(row),
                *(found.cells.get((row, column), "") for column in found.modules),
            )
            for row in found.modules
        )
        lines.extend(
            [
                f"#### Dependency Matrix: {escape_markdown(layer)}",
                "",
                render_markdown_table(
                    Table(
                        headers=("Module", *(_module(m) for m in found.modules)),
                        rows=rows,
                    )
                ),
                "",
            ]
        )
    return lines


def _module(name: str) -> str:
    """A module name as code: ``__init__`` would otherwise render bold."""
    return f"`{name}`"


def _pair(reference: str, target: str) -> str:
    return f"{reference} / {target}"


def _instability(value: ModuleMetrics | None) -> str:
    if value is None or value.instability is None:
        return "n/a"
    return f"{value.instability:.2f}"


def _metric_lines(architecture: Mapping[str, Any]) -> List[str]:
    layers = [layer for layer in INTERNAL_LAYERS if layer in architecture]
    reference = metrics(layers_edges(architecture, layers, REFERENCE))
    target = metrics(layers_edges(architecture, layers, TARGET_KINDS))
    modules = sorted(set(reference) | set(target))
    if not modules:
        return []

    def count(found: dict[str, ModuleMetrics], module: str, name: str) -> str:
        # A module without edges on one side has none: 0, not unknown.
        return str(getattr(found.get(module, ModuleMetrics(0, 0)), name))

    rows = tuple(
        (
            _module(module),
            _pair(count(reference, module, "fan_in"), count(target, module, "fan_in")),
            _pair(
                count(reference, module, "fan_out"), count(target, module, "fan_out")
            ),
            _pair(
                _instability(reference.get(module)), _instability(target.get(module))
            ),
        )
        for module in modules
    )
    return [
        "#### Module Metrics (informative, not part of the verdict)",
        "",
        "Fan-in and fan-out count the distinct modules using a module and used "
        "by it; instability is fan-out / (fan-in + fan-out). Coupling numbers "
        "do not tell whether the intended structure holds.",
        "",
        render_markdown_table(
            Table(
                headers=(
                    "Module",
                    "Fan-in (reference / target)",
                    "Fan-out (reference / target)",
                    "Instability (reference / target)",
                ),
                rows=rows,
            )
        ),
        "",
    ]


def _edge_list(edges: Sequence[tuple[str, str]], by_design: frozenset[Any]) -> str:
    items = [
        f"`{a} -> {b}`" + (" (also in the reference)" if (a, b) in by_design else "")
        for a, b in edges
    ]
    return "; ".join(_capped(items))


def _static_runtime_lines(compared: Sequence[Any]) -> List[str]:
    found = architectures(compared)
    static = next((a for code, a in found.items() if code.startswith("DEP")), None)
    runtime = next((a for code, a in found.items() if code.startswith("DYN")), None)
    if static is None or runtime is None:
        return []
    if not any(layer in static for layer in STATIC_LAYERS) or not any(
        layer in runtime for layer in RUNTIME_LAYERS
    ):
        return []
    diff = static_runtime(static, runtime)
    lines = [
        "### Static vs Runtime",
        "",
        "The target's module edges by where they show. An edge only imported "
        "may be a dead import, an import for annotations, or one no case "
        "exercised; an edge seen only at run time comes without an import (an "
        'injected object, a computed import, a callback). "also in the '
        'reference" marks an edge the reference shows the same way.',
        "",
        f"- Imported and used at run time: {diff.both}",
    ]
    if diff.static_only:
        lines.append(
            "- Imported only: "
            + _edge_list(diff.static_only, diff.reference_static_only)
        )
    if diff.runtime_only:
        lines.append(
            "- At run time only: "
            + _edge_list(diff.runtime_only, diff.reference_runtime_only)
        )
    return [*lines, ""]


def architecture_lines(results: Iterable[Any]) -> List[str]:
    """The section for ``results``; empty when none carries a model comparison."""
    compared = sorted(
        (r for r in results if _architecture(r) is not None),
        key=lambda r: str(r.rule_id),
    )
    if not compared:
        return []
    lines: List[str] = [
        "## Architecture",
        "",
        "The target against the reference's module dependencies "
        "(`architecture_entry`): an edge both have converges, one only the "
        "target has diverges, one only the reference has is absent. In a "
        "dependency matrix a row uses a column: `=` convergent, `+` divergent, "
        "`-` absent, `?` undecided, `a` allowed by an exception.",
        "",
    ]
    for result in compared:
        architecture = _architecture(result) or {}
        details = result.details
        lines.extend([_heading(result), ""])
        policy = details.get("policy")
        if policy:
            lines.append(f"- Policy: `{escape_markdown(str(policy))}`")
        if details.get("summary"):
            lines.append(f"- Summary: {escape_markdown(str(details['summary']))}")
        lines.append("")
        rows = tuple(
            (str(layer), *(str(len((diff or {}).get(kind) or [])) for kind in _KINDS))
            for layer, diff in architecture.items()
        )
        lines.append(
            render_markdown_table(
                Table(
                    headers=(
                        "Layer",
                        "Convergent",
                        "Divergent",
                        "Absent",
                        "Undecided",
                        "Allowed",
                    ),
                    rows=rows,
                )
            )
        )
        lines.append("")
        listed = [
            f"- {title}: " + "; ".join(items)
            for kind, title in _LISTED
            if (items := _listed(architecture, kind))
        ]
        if listed:
            lines.extend([*listed, ""])
        lines.extend(_matrix_lines(architecture))
        lines.extend(_metric_lines(architecture))
    lines.extend(_static_runtime_lines(compared))
    return lines


def across_targets_lines(targets: Iterable[Any]) -> List[str]:
    """Edges several targets of a run share, most shared first (F3.4)."""
    per_target = [architectures(getattr(t, "results", ()) or ()) for t in targets]
    if sum(1 for rules in per_target if rules) < 2:
        return []
    shared = [s for s in aggregate(per_target) if s.targets >= 2]
    if not shared:
        return []
    rows = tuple(
        (
            _rule_name(s.rule),
            s.layer,
            s.kind,
            f"`{s.edge}`",
            f"{s.targets}/{s.of} ({s.share:.0%})",
            (
                "check the model"
                if s.kind in _MODEL_SUSPECT_KINDS
                and s.share >= _MODEL_SUSPECT_SHARE
                and s.of >= _MODEL_SUSPECT_TARGETS
                else ""
            ),
        )
        for s in shared[:_MAX_LISTED]
    )
    lines = [
        "## Architecture Across Targets",
        "",
        "Edges several targets share. An edge nearly every target diverges on "
        f"(at least {_MODEL_SUSPECT_SHARE:.0%} of {_MODEL_SUSPECT_TARGETS} or more "
        "targets) may be one the model lacks rather than a mistake in each "
        "solution; an absent edge nearly every target lacks may be one the "
        'model should not require. Both are marked "check the model"; an '
        "undecided edge is not, since the policy leaves it open.",
        "",
        render_markdown_table(
            Table(
                headers=("Rule", "Layer", "Kind", "Edge", "Targets", "Note"),
                rows=rows,
            )
        ),
        "",
    ]
    if len(shared) > _MAX_LISTED:
        # After the blank line: a line right under a table is one more row.
        lines.extend([f"(+{len(shared) - _MAX_LISTED} more)", ""])
    return lines


def undecided_lines(results: Iterable[Any]) -> List[str]:
    """The count of passes that left architecture changes for a person to judge."""
    total = sum(
        1
        for result in results
        if result.status == "OK"
        and (getattr(result, "details", None) or {}).get("undecided")
    )
    if not total:
        return []
    return [
        f"- Passed With Undecided Architecture Changes: {total} "
        "(see `details.undecided`)"
    ]


__all__ = ["across_targets_lines", "architecture_lines", "undecided_lines"]
