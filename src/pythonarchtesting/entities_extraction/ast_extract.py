from __future__ import annotations

import ast
from pathlib import Path
from typing import Any, Optional, Sequence

from pythonarchtesting.entities import (
    AnnotationDeclaration,
    Entity,
    EntityKind,
    Role,
    build_canonical_id,
    hash_text,
    normalize_docstring,
    signature_key_from_info,
)
from pythonarchtesting.protocols.reference_resolution import normalize_reference

from .annotations import (
    extract_annotation_declarations,
    extract_function_body_annotation_declarations,
    extract_signature_annotation_declarations,
)
from .fingerprint import ast_fingerprint_from_body, source_hash_from_segment
from .paths import module_path_from_file
from .signature import (
    _annotation_strings,
    _line_text_from_source,
    signature_info_from_ast,
)


def _decorator_name(node: ast.AST) -> str | None:
    target = node.func if isinstance(node, ast.Call) else node
    if isinstance(target, ast.Attribute):
        return target.attr
    if isinstance(target, ast.Name):
        return target.id
    return None


class _EntityExtractor(ast.NodeVisitor):
    def __init__(
        self,
        module_path: str,
        filepath_rel: str,
        role: Role,
        root_label: str,
        file_text: str,
        include_nested_functions: bool,
    ) -> None:
        self.module_path = module_path
        self.filepath_rel = filepath_rel
        self.role = role
        self.root_label = root_label
        self.file_text = file_text
        self.include_nested_functions = include_nested_functions
        self.entities: list[Entity] = []
        self.non_matchable_entities: list[Entity] = []
        self._scope: list[tuple[str, str]] = []
        self._function_stack: list[Entity] = []
        self._module_aliases: dict[str, str] = {}

    def _body_annotation_declarations(
        self, body: Sequence[ast.stmt]
    ) -> list[AnnotationDeclaration]:
        return extract_annotation_declarations(body, self.file_text)

    def _function_annotation_declarations(
        self, node: ast.FunctionDef | ast.AsyncFunctionDef
    ) -> list[AnnotationDeclaration]:
        signature_declarations = extract_signature_annotation_declarations(
            node, self.file_text
        )
        body_declarations = extract_function_body_annotation_declarations(
            node.body, self.file_text
        )
        body_keys = {
            (
                declaration.kind,
                declaration.surface,
                declaration.subject_kind,
                declaration.subject_index,
                declaration.subject_name,
            )
            for declaration in body_declarations
            if declaration.kind and declaration.kind != "unknown"
        }
        if body_keys:
            signature_declarations = [
                declaration
                for declaration in signature_declarations
                if (
                    declaration.kind,
                    declaration.surface,
                    declaration.subject_kind,
                    declaration.subject_index,
                    declaration.subject_name,
                )
                not in body_keys
            ]
        return [*signature_declarations, *body_declarations]

    def _qualname(self, name: str) -> str:
        if not self._scope:
            return name
        return ".".join([item[0] for item in self._scope] + [name])

    def _in_function_scope(self) -> bool:
        return any(scope_type == "function" for _, scope_type in self._scope)

    def _current_parent(self) -> Optional[str]:
        if not self._scope:
            return None
        return self._scope[-1][1]

    def _current_function_entity(self) -> Optional[Entity]:
        if not self._function_stack:
            return None
        return self._function_stack[-1]

    def _mark_parent_nested(self, parent: Entity, nested: Entity) -> None:
        meta = parent.surface_meta
        meta["nested"] = True
        functions = meta.get("nested_functions")
        if functions is None:
            functions = []
            meta["nested_functions"] = functions
        functions.append(
            {
                "name": nested.name,
                "qualname": nested.qualname,
                "kind": nested.kind,
                "lineno": nested.lineno,
                "signature_key": nested.signature_key,
                "module_path": nested.module_path,
            }
        )

    def _build_entity_meta(self, decorator_list: Sequence[ast.AST]) -> dict[str, Any]:
        names = {_decorator_name(node) for node in decorator_list}
        meta: dict[str, Any] = {}
        if "property" in names:
            meta["property"] = True
        if "staticmethod" in names:
            meta["method_kind"] = "static"
        elif "classmethod" in names:
            meta["method_kind"] = "class"
        return meta

    def _class_bases(self, node: ast.ClassDef) -> list[str]:
        bases: list[str] = []
        for base in node.bases:
            base_expr = ast.unparse(base)
            normalized, _ = normalize_reference(
                base_expr,
                module_path=self.module_path,
                aliases=self._module_aliases,
            )
            bases.append(normalized or base_expr)
        return bases

    def _import_aliases(self, node: ast.Module) -> dict[str, str]:
        aliases: dict[str, str] = {}
        for stmt in node.body:
            if isinstance(stmt, ast.Import):
                for alias in stmt.names:
                    local_name = alias.asname or alias.name.split(".", 1)[0]
                    target_name = (
                        alias.name if alias.asname else alias.name.split(".", 1)[0]
                    )
                    aliases[local_name] = target_name
            elif isinstance(stmt, ast.ImportFrom) and stmt.module:
                for alias in stmt.names:
                    if alias.name == "*":
                        continue
                    aliases[alias.asname or alias.name] = f"{stmt.module}.{alias.name}"
        return aliases

    def _build_module_entity(self, node: ast.Module) -> Entity:
        docstring = normalize_docstring(ast.get_docstring(node, clean=True))
        doc_hash = hash_text(docstring) if docstring else None
        fingerprint, bag = ast_fingerprint_from_body(node.body)
        source_hash = source_hash_from_segment(self.file_text)
        line_text = _line_text_from_source(self.file_text, 1)
        module_name = self.module_path.rsplit(".", 1)[-1] if self.module_path else ""
        if not module_name:
            module_name = Path(self.filepath_rel).stem or "<module>"
        canonical_id = build_canonical_id(
            self.role,
            self.root_label,
            self.module_path,
            self.module_path,
            "module",
            "-",
        )
        return Entity(
            role=self.role,
            kind="module",
            root_label=self.root_label,
            module_path=self.module_path,
            qualname=self.module_path,
            name=module_name,
            filepath_rel=self.filepath_rel,
            lineno=1 if self.file_text else 0,
            signature=None,
            signature_key="-",
            ast_fingerprint=fingerprint,
            source_hash=source_hash,
            doc_hash=doc_hash,
            decorators_meta={},
            annotation_declarations=self._body_annotation_declarations(node.body),
            canonical_id=canonical_id,
            extras={
                "ast_tokens_bag": bag,
                "docstring": docstring,
                "ast_node": node,
                "line_text": line_text,
            },
        )

    def visit_Module(self, node: ast.Module) -> Any:
        self._module_aliases = self._import_aliases(node)
        self.entities.append(self._build_module_entity(node))
        for stmt in node.body:
            self.visit(stmt)

    def visit_ClassDef(self, node: ast.ClassDef) -> Any:
        qualname = self._qualname(node.name)
        docstring = normalize_docstring(ast.get_docstring(node, clean=True))
        doc_hash = hash_text(docstring) if docstring else None
        fingerprint, bag = ast_fingerprint_from_body(node.body)
        source_segment = ast.get_source_segment(self.file_text, node) or ""
        source_hash = source_hash_from_segment(source_segment)
        decorators_meta = self._build_entity_meta(node.decorator_list)
        signature_key = "-"
        canonical_id = build_canonical_id(
            self.role,
            self.root_label,
            self.module_path,
            qualname,
            "class",
            signature_key,
        )
        line_text = _line_text_from_source(self.file_text, getattr(node, "lineno", 0))
        entity = Entity(
            role=self.role,
            kind="class",
            root_label=self.root_label,
            module_path=self.module_path,
            qualname=qualname,
            name=node.name,
            filepath_rel=self.filepath_rel,
            lineno=getattr(node, "lineno", 0),
            signature=None,
            signature_key=signature_key,
            ast_fingerprint=fingerprint,
            source_hash=source_hash,
            doc_hash=doc_hash,
            decorators_meta=decorators_meta,
            annotation_declarations=self._body_annotation_declarations(node.body),
            canonical_id=canonical_id,
            extras={
                "bases": self._class_bases(node),
                "ast_tokens_bag": bag,
                "docstring": docstring,
                "ast_node": node,
                "line_text": line_text,
            },
        )
        self.entities.append(entity)
        self._scope.append((node.name, "class"))
        self.generic_visit(node)
        self._scope.pop()

    def _build_function_entity(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        kind: EntityKind,
        nested: bool,
    ) -> Entity:
        qualname = self._qualname(node.name)
        docstring = normalize_docstring(ast.get_docstring(node, clean=True))
        doc_hash = hash_text(docstring) if docstring else None
        fingerprint, bag = ast_fingerprint_from_body(node.body)
        source_segment = ast.get_source_segment(self.file_text, node) or ""
        source_hash = source_hash_from_segment(source_segment)
        signature = signature_info_from_ast(node)
        signature_key = signature_key_from_info(signature)
        decorators_meta = self._build_entity_meta(node.decorator_list)
        if nested:
            decorators_meta["nested"] = True
        annotations = _annotation_strings(node, skip_first_arg=(kind == "method"))
        line_text = _line_text_from_source(self.file_text, getattr(node, "lineno", 0))
        canonical_id = build_canonical_id(
            self.role,
            self.root_label,
            self.module_path,
            qualname,
            kind,
            signature_key,
        )
        return Entity(
            role=self.role,
            kind=kind,
            root_label=self.root_label,
            module_path=self.module_path,
            qualname=qualname,
            name=node.name,
            filepath_rel=self.filepath_rel,
            lineno=getattr(node, "lineno", 0),
            signature=signature,
            signature_key=signature_key,
            ast_fingerprint=fingerprint,
            source_hash=source_hash,
            doc_hash=doc_hash,
            decorators_meta=decorators_meta,
            annotation_declarations=self._function_annotation_declarations(node),
            canonical_id=canonical_id,
            extras={
                "ast_tokens_bag": bag,
                "docstring": docstring,
                "annotations": annotations,
                "ast_node": node,
                "line_text": line_text,
            },
        )

    def _handle_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        parent = self._current_parent()
        kind: EntityKind = "function"
        if parent == "class":
            kind = "method"

        is_nested = self._in_function_scope()
        if is_nested and not self.include_nested_functions:
            entity = self._build_function_entity(node, kind, nested=True)
            self.non_matchable_entities.append(entity)
            parent_entity = self._current_function_entity()
            if parent_entity is not None:
                self._mark_parent_nested(parent_entity, entity)

            self._scope.append((node.name, "function"))
            self._function_stack.append(entity)
            self.generic_visit(node)
            self._function_stack.pop()
            self._scope.pop()
            return

        entity = self._build_function_entity(node, kind, nested=False)
        self.entities.append(entity)
        self._scope.append((node.name, "function"))
        self._function_stack.append(entity)
        self.generic_visit(node)
        self._function_stack.pop()
        self._scope.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> Any:
        self._handle_function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> Any:
        self._handle_function(node)


def extract_entities_from_ast(
    tree: ast.Module,
    file_text: str,
    file_path: Path,
    root_path: Path,
    target_module_name: Optional[str],
    role: Role,
    include_nested_functions: bool,
    root_label: str = "root",
) -> list[Entity]:
    matchable, _ = extract_entities_from_ast_with_nonmatchable(
        tree,
        file_text,
        file_path,
        root_path,
        target_module_name,
        role,
        include_nested_functions,
        root_label=root_label,
    )
    return matchable


def extract_entities_from_ast_with_nonmatchable(
    tree: ast.Module,
    file_text: str,
    file_path: Path,
    root_path: Path,
    target_module_name: Optional[str],
    role: Role,
    include_nested_functions: bool,
    root_label: str = "root",
) -> tuple[list[Entity], list[Entity]]:
    module_path, filepath_rel = module_path_from_file(
        file_path, root_path, target_module_name
    )
    extractor = _EntityExtractor(
        module_path,
        filepath_rel,
        role,
        root_label,
        file_text,
        include_nested_functions,
    )
    extractor.visit(tree)
    return extractor.entities, extractor.non_matchable_entities


def extract_entities_from_source(
    source_text: str,
    file_path: Path,
    root_path: Path,
    target_module_name: Optional[str],
    role: Role,
    include_nested_functions: bool,
    root_label: str = "root",
) -> list[Entity]:
    matchable, _ = extract_entities_from_source_with_nonmatchable(
        source_text,
        file_path,
        root_path,
        target_module_name,
        role,
        include_nested_functions,
        root_label=root_label,
    )
    return matchable


def extract_entities_from_source_with_nonmatchable(
    source_text: str,
    file_path: Path,
    root_path: Path,
    target_module_name: Optional[str],
    role: Role,
    include_nested_functions: bool,
    root_label: str = "root",
) -> tuple[list[Entity], list[Entity]]:
    tree = ast.parse(source_text)
    return extract_entities_from_ast_with_nonmatchable(
        tree,
        source_text,
        file_path,
        root_path,
        target_module_name,
        role,
        include_nested_functions,
        root_label=root_label,
    )


__all__ = [
    "extract_entities_from_ast",
    "extract_entities_from_ast_with_nonmatchable",
    "extract_entities_from_source",
    "extract_entities_from_source_with_nonmatchable",
]
