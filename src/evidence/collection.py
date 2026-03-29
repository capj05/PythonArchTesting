"""
Shared evidence collection helpers for static analysis.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.config import Config
from src.entities_extraction import module_path_from_file
from src.evidence.static_ast import collect_call_sites, collect_import_graph
from src.util.discovery_utils import discover_python_files


@dataclass(frozen=True)
class ParsedModule:
    file_path: Path
    file_text: str
    tree: ast.Module
    module_path: str
    filepath_rel: str


def parse_python_modules(
    *,
    root_path: Path,
    config: Config,
    target_module_name: Optional[str],
) -> tuple[List[ParsedModule], List[tuple[Path, SyntaxError]]]:
    parsed_modules: List[ParsedModule] = []
    errors: List[tuple[Path, SyntaxError]] = []

    for file_path in discover_python_files(root_path, config):
        path_obj = Path(file_path)
        try:
            file_text = path_obj.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(file_text, filename=str(path_obj))
        except SyntaxError as exc:
            errors.append((path_obj, exc))
            continue

        module_path, filepath_rel = module_path_from_file(
            path_obj, root_path, target_module_name
        )
        parsed_modules.append(
            ParsedModule(
                file_path=path_obj,
                file_text=file_text,
                tree=tree,
                module_path=module_path,
                filepath_rel=filepath_rel,
            )
        )

    return parsed_modules, errors


def collect_static_evidence(
    *,
    root_path: Path,
    config: Config,
    target_module_name: Optional[str],
    parsed_modules: Optional[List[ParsedModule]] = None,
) -> Dict[str, Any]:
    import_edges: List[Dict[str, Any]] = []
    call_sites: List[Dict[str, Any]] = []
    module_paths: List[str] = []

    if parsed_modules is None:
        parsed_modules, _ = parse_python_modules(
            root_path=root_path,
            config=config,
            target_module_name=target_module_name,
        )

    for parsed in parsed_modules:
        for edge in collect_import_graph(parsed.tree):
            import_edges.append(
                {
                    "kind": edge.kind,
                    "module": edge.module,
                    "name": edge.name,
                    "asname": edge.asname,
                    "lineno": edge.lineno,
                    "filepath": parsed.filepath_rel,
                }
            )

        for site in collect_call_sites(parsed.tree):
            call_sites.append(
                {
                    "callee": site.callee,
                    "lineno": site.lineno,
                    "filepath": parsed.filepath_rel,
                }
            )

        if parsed.module_path:
            module_paths.append(parsed.module_path)

    import_edges_sorted = sorted(
        import_edges,
        key=lambda e: (
            e.get("filepath", ""),
            e.get("lineno", 0),
            e.get("module", ""),
            e.get("name") or "",
            e.get("asname") or "",
        ),
    )
    call_sites_sorted = sorted(
        call_sites,
        key=lambda c: (
            c.get("filepath", ""),
            c.get("lineno", 0),
            c.get("callee", ""),
        ),
    )
    module_paths_sorted = sorted(set(module_paths))

    return {
        "import_edges": import_edges_sorted,
        "call_sites": call_sites_sorted,
        "modules": module_paths_sorted,
    }


__all__ = [
    "ParsedModule",
    "parse_python_modules",
    "collect_static_evidence",
]
