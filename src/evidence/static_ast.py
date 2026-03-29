"""
Static AST evidence collection utilities.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import Any, Dict, List, Literal, Optional, Tuple

ImportKind = Literal["import", "importfrom"]


@dataclass(frozen=True)
class ImportEdge:
    kind: ImportKind
    module: str
    name: Optional[str]
    asname: Optional[str]
    lineno: int


@dataclass(frozen=True)
class CallSite:
    callee: str
    lineno: int


@dataclass(frozen=True)
class DynamicImportCallSite:
    callee: str
    lineno: int
    literal_target: Optional[str]
    unknown_dynamic_target: bool


@dataclass(frozen=True)
class ClassSummary:
    module_path: str
    class_name: str
    qualname: str
    lineno: int
    bases: List[str]
    methods: List[Dict[str, Any]]
    instance_attr_assignments: List[str]
    class_attr_assignments: List[str]


@dataclass(frozen=True)
class InstantiationSite:
    callee: str
    lineno: int
    scope: str  # "module", "function", "method"
    assigned_target: Optional[str]


@dataclass(frozen=True)
class FunctionSummary:
    module_path: str
    qualname: str
    name: str
    lineno: int
    branch_count: int
    return_calls: List[Dict[str, Any]]
    decorators: List[str]
    calls: List[Dict[str, Any]]


def collect_import_graph(tree: ast.AST) -> List[ImportEdge]:
    """
    Collect import edges from an AST.
    """
    edges: List[ImportEdge] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name:
                    edges.append(
                        ImportEdge(
                            kind="import",
                            module=alias.name,
                            name=None,
                            asname=alias.asname,
                            lineno=getattr(node, "lineno", 0),
                        )
                    )
        elif isinstance(node, ast.ImportFrom):
            level = getattr(node, "level", 0) or 0
            prefix = "." * level
            module = prefix + (node.module or "")
            for alias in node.names:
                edges.append(
                    ImportEdge(
                        kind="importfrom",
                        module=module,
                        name=alias.name if alias.name else None,
                        asname=alias.asname,
                        lineno=getattr(node, "lineno", 0),
                    )
                )

    edges.sort(key=lambda e: (e.module, e.name or "", e.lineno, e.asname or ""))
    return edges


def _normalize_callee(node: ast.AST) -> Optional[str]:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parts: List[str] = []
        cur: ast.AST = node
        while isinstance(cur, ast.Attribute):
            parts.append(cur.attr)
            cur = cur.value
        if isinstance(cur, ast.Name):
            parts.append(cur.id)
            return ".".join(reversed(parts))
    return None


def collect_call_sites(tree: ast.AST) -> List[CallSite]:
    """
    Collect call sites for a safe subset of patterns.
    """
    sites: List[CallSite] = []

    allowed = {
        "open",
        "__import__",
        "os.system",
        "subprocess.Popen",
        "importlib.import_module",
    }

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        callee = _normalize_callee(node.func)
        if callee is None or callee not in allowed:
            continue
        sites.append(
            CallSite(
                callee=callee,
                lineno=getattr(node, "lineno", 0),
            )
        )

    sites.sort(key=lambda s: (s.callee, s.lineno))
    return sites


def collect_dynamic_import_call_sites(
    tree: ast.AST, forbidden_callees: set[str]
) -> List[DynamicImportCallSite]:
    """
    Collect dynamic import call sites for configured forbidden callees.
    """
    sites: List[DynamicImportCallSite] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        callee = _normalize_callee(node.func)
        if callee is None or callee not in forbidden_callees:
            continue

        literal_target: Optional[str] = None
        unknown_dynamic_target = True
        if node.args:
            first_arg = node.args[0]
            if isinstance(first_arg, ast.Constant) and isinstance(first_arg.value, str):
                literal_target = first_arg.value
                unknown_dynamic_target = False
            elif getattr(ast, "Str", None) is not None and isinstance(
                first_arg, ast.Str
            ):
                literal_target = first_arg.s
                unknown_dynamic_target = False

        sites.append(
            DynamicImportCallSite(
                callee=callee,
                lineno=getattr(node, "lineno", 0),
                literal_target=literal_target,
                unknown_dynamic_target=unknown_dynamic_target,
            )
        )

    sites.sort(key=lambda s: (s.lineno, s.callee, s.literal_target or ""))
    return sites


def _normalize_base_class(base: ast.AST) -> Optional[str]:
    """Normalize base class to string representation."""
    if isinstance(base, ast.Name):
        return base.id
    elif isinstance(base, ast.Attribute):
        parts = []
        cur = base
        while isinstance(cur, ast.Attribute):
            parts.append(cur.attr)
            cur = cur.value
        if isinstance(cur, ast.Name):
            parts.append(cur.id)
            return ".".join(reversed(parts))
    return None


def _is_method_decorator(node: ast.FunctionDef) -> str:
    """Determine method kind from decorators."""
    for decorator in node.decorator_list:
        if isinstance(decorator, ast.Name):
            if decorator.id == "classmethod":
                return "classmethod"
            elif decorator.id == "staticmethod":
                return "staticmethod"
        elif isinstance(decorator, ast.Attribute):
            if (
                isinstance(decorator.value, ast.Name)
                and decorator.value.id == "property"
            ):
                return "property"
    return "instance"


def collect_class_summaries(tree: ast.AST, module_path: str) -> List[ClassSummary]:
    """Collect class summaries for singleton detection."""
    summaries: List[ClassSummary] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue

        # Collect base classes
        bases = []
        for base in node.bases:
            normalized = _normalize_base_class(base)
            if normalized:
                bases.append(normalized)

        # Collect methods
        methods = []
        instance_attrs = set()
        class_attrs = set()

        for item in node.body:
            if isinstance(item, ast.FunctionDef):
                method_kind = _is_method_decorator(item)
                methods.append(
                    {
                        "name": item.name,
                        "kind": method_kind,
                        "lineno": item.lineno,
                    }
                )

                # Look for self.attr = ... and cls.attr = ... patterns
                for stmt in ast.walk(item):
                    if isinstance(stmt, ast.Assign):
                        for target in stmt.targets:
                            if isinstance(target, ast.Attribute):
                                # Check if it's self.attr or cls.attr
                                if isinstance(target.value, ast.Name):
                                    if target.value.id == "self":
                                        instance_attrs.add(target.attr)
                                    elif target.value.id == "cls":
                                        class_attrs.add(target.attr)

            elif isinstance(item, ast.Assign):
                # Class-level attribute assignments
                for target in item.targets:
                    if isinstance(target, ast.Name):
                        class_attrs.add(target.id)

        summary = ClassSummary(
            module_path=module_path,
            class_name=node.name,
            qualname=node.name,
            lineno=node.lineno,
            bases=bases,
            methods=methods,
            instance_attr_assignments=sorted(instance_attrs),
            class_attr_assignments=sorted(class_attrs),
        )
        summaries.append(summary)

    summaries.sort(key=lambda s: (s.module_path, s.class_name, s.lineno))
    return summaries


def collect_instantiation_sites(tree: ast.AST) -> List[InstantiationSite]:
    """Collect instantiation sites for singleton detection."""
    sites: List[InstantiationSite] = []

    # Track scope context with proper parent tracking
    scope_stack: List[Tuple[str, ast.AST]] = [("module", tree)]

    def _get_scope() -> str:
        return scope_stack[-1][0] if scope_stack else "module"

    def _get_assigned_target_name(node: ast.AST) -> Optional[str]:
        """Extract assigned target name from assignment context."""
        # Walk up to find containing assignment
        for parent in ast.walk(tree):
            if isinstance(parent, (ast.Assign, ast.AnnAssign)):
                if hasattr(parent, "value") and parent.value == node:
                    if isinstance(parent, ast.Assign):
                        for target in parent.targets:
                            if isinstance(target, ast.Name):
                                return target.id
                    elif isinstance(parent, ast.AnnAssign):
                        if isinstance(parent.target, ast.Name):
                            return parent.target.id
        return None

    # Walk the tree with proper scope tracking
    class ScopeVisitor(ast.NodeVisitor):
        def generic_visit(self, node):
            # Update scope before visiting children
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                scope_stack.append(("function", node))
            elif isinstance(node, ast.ClassDef):
                scope_stack.append(("class", node))

            # Visit children
            super().generic_visit(node)

            # Pop scope after visiting children
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                if len(scope_stack) > 1:  # Keep root module scope
                    scope_stack.pop()

        def visit_Call(self, node):
            callee = _normalize_callee(node.func)
            if callee:
                # Check if this looks like a class instantiation
                # (heuristic: callee is a simple name, not a module.function)
                if "." not in callee or callee.split(".")[0].isupper():
                    site = InstantiationSite(
                        callee=callee,
                        lineno=getattr(node, "lineno", 0),
                        scope=_get_scope(),
                        assigned_target=_get_assigned_target_name(node),
                    )
                    sites.append(site)
            self.generic_visit(node)

    visitor = ScopeVisitor()
    visitor.visit(tree)

    sites.sort(key=lambda s: (s.lineno, s.callee, s.scope))
    return sites


def collect_function_summaries(
    tree: ast.AST, module_path: str
) -> List[FunctionSummary]:
    """Collect function summaries for factory method detection."""
    summaries: List[FunctionSummary] = []

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            # Count branches (if statements)
            branch_count = 0
            for child in ast.walk(node):
                if isinstance(child, ast.If):
                    branch_count += 1

            # Collect return calls
            return_calls = []
            for child in ast.walk(node):
                if isinstance(child, ast.Return) and child.value:
                    if isinstance(child.value, ast.Call):
                        callee = _normalize_callee(child.value.func)
                        if callee:
                            return_calls.append(
                                {"callee": callee, "lineno": child.lineno}
                            )

            # Collect decorators
            decorators = []
            for decorator in node.decorator_list:
                if isinstance(decorator, ast.Name):
                    decorators.append(decorator.id)
                elif isinstance(decorator, ast.Attribute):
                    decorators.append(_normalize_callee(decorator) or "unknown")

            # Collect calls (subset for factory detection)
            calls = []
            for child in ast.walk(node):
                if isinstance(child, ast.Call):
                    callee = _normalize_callee(child.func)
                    if callee:
                        calls.append({"callee": callee, "lineno": child.lineno})

            # Determine qualname based on context
            qualname = node.name
            # Simple heuristic: if parent is a class, add class name prefix
            for parent in ast.walk(tree):
                if isinstance(parent, ast.ClassDef):
                    if node in parent.body:
                        qualname = f"{parent.name}.{node.name}"
                        break

            summary = FunctionSummary(
                module_path=module_path,
                qualname=qualname,
                name=node.name,
                lineno=node.lineno,
                branch_count=branch_count,
                return_calls=sorted(
                    return_calls, key=lambda r: (r["lineno"], r["callee"])
                ),
                decorators=sorted(set(decorators)),
                calls=sorted(calls, key=lambda c: (c["lineno"], c["callee"])),
            )
            summaries.append(summary)

    summaries.sort(key=lambda s: (s.module_path, s.qualname, s.lineno))
    return summaries


def evidence_import_graph(
    *,
    role: str,
    module_path: str,
    filepath_rel: str,
    edges: List[ImportEdge],
) -> Dict[str, Any]:
    imports = [
        {
            "kind": edge.kind,
            "module": edge.module,
            "name": edge.name,
            "asname": edge.asname,
            "lineno": edge.lineno,
        }
        for edge in edges
    ]
    imports.sort(
        key=lambda item: (
            item.get("module", ""),
            item.get("name") or "",
            item.get("lineno", 0),
            item.get("asname") or "",
        )
    )
    payload = {
        "module_path": module_path,
        "filepath": filepath_rel,
        "imports": imports,
    }
    return {
        "type": "ast_import_graph",
        "payload": payload,
        "source": "ast",
        "role": role,
    }


def evidence_call_sites(
    *,
    role: str,
    module_path: str,
    filepath_rel: str,
    sites: List[CallSite],
) -> Dict[str, Any]:
    calls = [{"callee": site.callee, "lineno": site.lineno} for site in sites]
    calls.sort(key=lambda item: (item.get("callee", ""), item.get("lineno", 0)))
    payload = {
        "module_path": module_path,
        "filepath": filepath_rel,
        "calls": calls,
    }
    return {"type": "ast_call_sites", "payload": payload, "source": "ast", "role": role}


def evidence_class_summaries(
    *,
    role: str,
    module_path: str,
    filepath_rel: str,
    summaries: List[ClassSummary],
) -> Dict[str, Any]:
    """Build evidence payload for class summaries."""
    classes = [
        {
            "module_path": summary.module_path,
            "class_name": summary.class_name,
            "qualname": summary.qualname,
            "lineno": summary.lineno,
            "bases": summary.bases,
            "methods": summary.methods,
            "instance_attr_assignments": summary.instance_attr_assignments,
            "class_attr_assignments": summary.class_attr_assignments,
        }
        for summary in summaries
    ]
    classes.sort(key=lambda item: (item.get("class_name", ""), item.get("lineno", 0)))
    payload = {
        "module_path": module_path,
        "filepath": filepath_rel,
        "classes": classes,
    }
    return {
        "type": "ast_class_summary",
        "payload": payload,
        "source": "ast",
        "role": role,
    }


def evidence_instantiation_sites(
    *,
    role: str,
    module_path: str,
    filepath_rel: str,
    sites: List[InstantiationSite],
) -> Dict[str, Any]:
    """Build evidence payload for instantiation sites."""
    instantiations = [
        {
            "callee": site.callee,
            "lineno": site.lineno,
            "scope": site.scope,
            "assigned_target": site.assigned_target,
        }
        for site in sites
    ]
    instantiations.sort(
        key=lambda item: (
            item.get("lineno", 0),
            item.get("callee", ""),
            item.get("scope", ""),
        )
    )
    payload = {
        "module_path": module_path,
        "filepath": filepath_rel,
        "sites": instantiations,
    }
    return {
        "type": "ast_instantiation_sites",
        "payload": payload,
        "source": "ast",
        "role": role,
    }


def evidence_function_summaries(
    *,
    role: str,
    module_path: str,
    filepath_rel: str,
    summaries: List[FunctionSummary],
) -> Dict[str, Any]:
    """Build evidence payload for function summaries."""
    functions = [
        {
            "module_path": summary.module_path,
            "qualname": summary.qualname,
            "name": summary.name,
            "lineno": summary.lineno,
            "branch_count": summary.branch_count,
            "return_calls": summary.return_calls,
            "decorators": summary.decorators,
            "calls": summary.calls,
        }
        for summary in summaries
    ]
    functions.sort(key=lambda item: (item.get("qualname", ""), item.get("lineno", 0)))
    payload = {
        "module_path": module_path,
        "filepath": filepath_rel,
        "functions": functions,
    }
    return {
        "type": "ast_function_summary",
        "payload": payload,
        "source": "ast",
        "role": role,
    }


__all__ = [
    "ImportKind",
    "ImportEdge",
    "CallSite",
    "DynamicImportCallSite",
    "ClassSummary",
    "InstantiationSite",
    "FunctionSummary",
    "collect_import_graph",
    "collect_call_sites",
    "collect_dynamic_import_call_sites",
    "collect_class_summaries",
    "collect_instantiation_sites",
    "collect_function_summaries",
    "evidence_import_graph",
    "evidence_call_sites",
    "evidence_class_summaries",
    "evidence_instantiation_sites",
    "evidence_function_summaries",
]
