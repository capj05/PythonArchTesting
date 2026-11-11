"""Which mutants verify each typical error of a task.

A typical error of a principle names the mutation ``operator`` that seeds it
and the marker that detects it (``detected_by``). Its mutants are the
operator's mutants anywhere in the reference (``seed_candidates``; for a
call-seeding operator, those making the call its signature names) that lie
in the entities the detecting check is on (``mutants_for``). What the cases of
the task's checks build tells the operators which classes a parameter holds
(``parameter_classes``) and which constructor parameters get a spy
(``spied``).
"""

from __future__ import annotations

from typing import Any, Optional

from pythonarchtesting.util.ast_utils import is_private

# The call each call-seeding operator inserts, for the callee an error's
# signature names: ``add_io_call`` any of the three I/O calls,
# ``add_io_via_helper`` only print, ``add_builtin_call`` also a type test.
_IO_MEMBERS = {
    "add_io_call": {
        "builtins:print": "print",
        "builtins:input": "input",
        "io:open": "open",
    },
    "add_io_via_helper": {"builtins:print": "print"},
    "add_builtin_call": {
        "builtins:print": "print",
        "builtins:input": "input",
        "io:open": "open",
        "builtins:isinstance": "isinstance",
        "builtins:type": "type",
    },
}
# What in the reference each operator needs, for a ``not_applicable`` error.
_SITES = {
    "foreign_write": (
        "data attribute of an object a function gets from outside (as a "
        "parameter or through a module global)"
    ),
    "mutate_private_container": (
        "private container (a dict, list or set an owner's method creates) "
        "of an object a function gets as a parameter or through a module global"
    ),
    "mutate_public_container": (
        "public container (a dict, list or set an owner's method creates) "
        "of an object a function gets as a parameter or through a module global"
    ),
    "read_private_attribute": (
        "private data attribute of an object of a project class a function "
        "gets as a parameter or through a module global"
    ),
    "stub_role_call": "call of a function of another project module",
    "add_io_call": "function whose body starts on a line of its own",
    "add_io_via_helper": "function whose body starts on a line of its own",
    "add_builtin_call": "function whose body starts on a line of its own",
    "drop_base": "class that names a base other than object",
    "hardcode_collaborator": (
        "constructor that keeps a collaborator it is given (self.x = x) together "
        "with a class of the check's modules that can be built without arguments"
    ),
    "concretize_base": (
        "abstract class (ABC, Protocol or ABCMeta among its bases, or an "
        "@abstractmethod method)"
    ),
}


def aimed_entities(error: Any, checks: list[Any], entities: dict[str, Any]) -> set[Any]:
    """``(file, qualname)`` of the entities the check detecting ``error`` is on;
    for an operator that changes a constructor, also the ``__init__`` a
    method's class inherits from a project base (``_constructor``)."""
    aimed = {
        (str(entities[c.entity_id].filepath_rel), str(entities[c.entity_id].qualname))
        for c in checks
        if c.marker == error.detected_by and c.not_applicable is None
    }
    if error.operator in _CONSTRUCTOR_OPERATORS:
        for file, qualname in list(aimed):
            owner = qualname.rpartition(".")[0]
            if owner:
                (where, cls), node = _constructor(entities, file, owner)
                if node is not None and cls != owner:
                    aimed.add((where, f"{cls}.__init__"))
    return aimed


def detector_modules(error: Any, checks: list[Any]) -> set[str]:
    """The modules the check detecting ``error`` names (with ``target_role``,
    those of the entities bound to that role, or their classes)."""
    return {
        str(module)
        for c in checks
        if c.marker == error.detected_by
        for module in c.params["modules"]
    }


def untargeted_reason(error: Any, checks: list[Any]) -> Optional[str]:
    """Why the check detecting ``error`` has nothing to check in the task,
    when it has not on any entity (``TaskCheck.not_applicable``)."""
    mine = [c for c in checks if c.marker == error.detected_by]
    if mine and all(c.not_applicable is not None for c in mine):
        return str(mine[0].not_applicable)
    return None


def spied(
    checks: list[Any], entities: dict[str, Any]
) -> dict[tuple[str, str], set[str]]:
    """The constructor parameters the task gives a spy: ``(file, class) ->
    parameter names`` for each ``{"$spy": ...}`` in the ``init`` of a
    method's checks, positional (after ``self``) or by keyword. The class is
    the one whose ``__init__`` keeps them: a project base's, when the
    method's class inherits its constructor."""
    found: dict[tuple[str, str], set[str]] = {}
    for check in checks:
        entity = entities.get(check.entity_id)
        init = check.params.get("init")
        if entity is None or entity.kind != "method" or not isinstance(init, dict):
            continue
        owner = str(entity.qualname).rpartition(".")[0]
        file = str(entity.filepath_rel)
        where, init_node = _constructor(entities, file, owner)
        names: list[str] = []
        if init_node is not None:
            names = [a.arg for a in init_node.args.posonlyargs + init_node.args.args][
                1:
            ]
            names += [a.arg for a in init_node.args.kwonlyargs]
        given = list(zip(names, init.get("args") or []))
        given += list((init.get("kwargs") or {}).items())
        # The parameters belong to the class whose constructor keeps them (a
        # project base, when the class inherits its constructor).
        params = found.setdefault(where, set())
        params.update(
            name for name, value in given if isinstance(value, dict) and "$spy" in value
        )
    return found


def _constructor(
    entities: dict[str, Any], file: str, owner: str
) -> tuple[tuple[str, str], Any]:
    """``((file, class), node)`` of the ``__init__`` objects of ``owner`` (in
    ``file``) run: its own, else the nearest project base's (a base named by
    one class of the reference only); ``node`` is ``None`` without one."""
    import ast

    classes: dict[str, list[Any]] = {}
    inits: dict[tuple[str, str], Any] = {}
    for other in entities.values():
        node = other.extras.get("ast_node")
        name = str(other.qualname)
        if other.kind == "class" and isinstance(node, ast.ClassDef):
            classes.setdefault(name.rpartition(".")[2], []).append(other)
        elif name.endswith(".__init__") and isinstance(
            node, (ast.FunctionDef, ast.AsyncFunctionDef)
        ):
            inits[(str(other.filepath_rel), name.rpartition(".")[0])] = node
    pending, seen = [(file, owner)], set()
    while pending:
        key = pending.pop(0)
        if key in seen:
            continue
        seen.add(key)
        if key in inits:
            return key, inits[key]
        found = [
            c
            for c in classes.get(key[1].rpartition(".")[2], [])
            if str(c.filepath_rel) == key[0] and str(c.qualname) == key[1]
        ]
        node = found[0].extras.get("ast_node") if found else None
        for base in getattr(node, "bases", []):
            name = base.id if isinstance(base, ast.Name) else getattr(base, "attr", "")
            named = classes.get(name, [])
            if len(named) == 1:
                pending.append((str(named[0].filepath_rel), str(named[0].qualname)))
    return (file, owner), None


def named_callees(error: Any, checks: list[Any]) -> list[str]:
    """The callees (``builtins:isinstance``) the check detecting ``error``
    names (``builtins.isinstance``)."""
    found: list[str] = []
    for module in sorted(detector_modules(error, checks)):
        head, _, last = module.rpartition(".")
        if head and f"{head}:{last}" not in found:
            found.append(f"{head}:{last}")
    return found


def seed_candidates(
    error: Any, mutants: list[Any], callees: Optional[list[str]] = None
) -> Optional[list[Any]]:
    """The mutants of ``error``'s operator anywhere in the reference (of a
    call-seeding operator, those making the call its signature names, or
    without one, a call of the ``callees`` its check names); ``None`` when
    the operator cannot make that call."""
    members: Optional[set[str]] = None
    callee = error.signature.callee if error.signature else None
    if error.operator in _IO_MEMBERS:
        wanted = [callee] if callee is not None else list(callees or [])
        if wanted:
            members = {
                _IO_MEMBERS[error.operator][c]
                for c in wanted
                if c in _IO_MEMBERS[error.operator]
            }
            if not members:
                return None
    # A write the signature declares private (or public) is seeded only into
    # such an attribute: one of the other kind would be another error.
    private = getattr(error.signature, "private", None)
    return [
        m
        for m in mutants
        if m.operator == error.operator
        and (members is None or m.member in members)
        and (
            private is None
            or error.operator != "foreign_write"
            or is_private(m.member) == private
        )
    ]


# Operators that change a constructor: a check on a method sees the change,
# because the method's cases build its object first. ``rebuild_injected``
# also changes a constructor, but no catalogue error seeds with it, and its
# mutants name no ``function`` to aim by.
_CONSTRUCTOR_OPERATORS = frozenset({"hardcode_collaborator"})


def _in_aimed(mutant: Any, aimed: set[Any]) -> bool:
    if (mutant.file, mutant.function) in aimed:
        return True
    if mutant.operator not in _CONSTRUCTOR_OPERATORS:
        return False
    owner, _, method = str(mutant.function).rpartition(".")
    return method == "__init__" and any(
        file == mutant.file and str(qualname).startswith(f"{owner}.")
        for file, qualname in aimed
    )


def mutants_for(
    error: Any, candidates: list[Any], aimed: set[Any], targets: set[str]
) -> list[Any]:
    """The ``candidates`` that seed ``error`` where its check looks. A mutant
    of ``stub_role_call`` stops the calls into a module the check names; one
    of a constructor operator changes the constructor of a method's class."""
    members = targets if error.operator == "stub_role_call" else None
    return [
        m
        for m in candidates
        if _in_aimed(m, aimed) and (members is None or m.member in members)
    ]


def parameter_classes(
    checks: list[Any], entities: dict[str, Any]
) -> dict[tuple[str, str], dict[str, str]]:
    """What the cases of the task's checks build for each function's
    parameters: ``(file, qualname) -> {parameter: class name}`` for every
    argument that is a project object (``{"$new": "inventory.Inventory"}``),
    positional (after ``self`` for a method) or by keyword."""
    import ast

    found: dict[tuple[str, str], dict[str, str]] = {}
    for check in checks:
        entity = entities.get(check.entity_id)
        if entity is None or check.params["cases"] is None:
            continue
        node = entity.extras.get("ast_node")
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        names = [a.arg for a in node.args.posonlyargs + node.args.args]
        if entity.kind == "method":
            names = names[1:]
        classes = found.setdefault((str(entity.filepath_rel), str(entity.qualname)), {})
        for case in check.params["cases"]:
            if not isinstance(case, dict):
                continue
            given = list(zip(names, case.get("args") or []))
            given += list((case.get("kwargs") or {}).items())
            for name, value in given:
                if isinstance(value, dict) and isinstance(value.get("$new"), str):
                    classes.setdefault(name, value["$new"].rpartition(".")[2])
    return found


def unread_files_note(skipped: list[tuple[str, str]]) -> str:
    """Why an error may have found nothing to seed: the files of the
    reference the operators could not read, which get no mutant (empty when
    every file was read)."""
    if not skipped:
        return ""
    files = "; ".join(f"{file} ({why})" for file, why in skipped)
    return f"; no mutant was made in files that do not decode or parse: {files}"


def unseedable_reason(error: Any, checks: list[Any]) -> str:
    """Why a call-seeding operator cannot seed ``error``: the callee its
    signature names, or, without one, the callees its check names."""
    callee = error.signature.callee if error.signature else None
    if callee:
        return f"{error.operator} cannot seed a call of {callee}"
    named = ", ".join(named_callees(error, checks)) or "no callee"
    return (
        f"{error.operator} cannot seed a call of any callee "
        f"{error.detected_by} names ({named})"
    )


def missing_site(error: Any) -> str:
    """What the reference would need for ``error``'s operator to seed it
    (for a ``not_applicable`` error); a write the signature declares private
    or public needs an attribute of that kind (``seed_candidates``)."""
    site = _SITES.get(str(error.operator), "place to seed the error")
    private = getattr(error.signature, "private", None)
    if error.operator == "foreign_write" and private is not None:
        site = ("private " if private else "public ") + site
    return site


__all__ = [
    "aimed_entities",
    "detector_modules",
    "missing_site",
    "mutants_for",
    "named_callees",
    "parameter_classes",
    "seed_candidates",
    "spied",
    "unread_files_note",
    "unseedable_reason",
    "untargeted_reason",
]
