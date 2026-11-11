"""Which project module an absolute module name names.

A project's modules are named relative to its root (``world``,
``space_a.actions``), but its code may import them under the root package's
own name (``game.world``) or under any package prefix. The callers apply
different rules on purpose, so each rule is a function of its own:

- ``project_module_under_package`` (mutation operators): the name itself, or
  the name under the root package ``package``, exactly;
- ``project_module_by_suffix`` (global mode's discovery): the longest tail
  of the name past any package prefix;
- ``strip_package``: the shared mechanic of the first, which the static
  private-access check uses too.

``dynamic/probe.py`` has a variant of its own (``_local_module``: the
package itself is ``__init__``): it runs as a standalone script and imports
no part of the framework.
"""

from __future__ import annotations

from collections.abc import Collection
from typing import Optional


def strip_package(name: str, package: Optional[str]) -> Optional[str]:
    """``name`` without the prefix ``package.``: ``""`` for the package
    itself, ``None`` when ``name`` is not in the package (or there is no
    ``package``)."""
    if package and name == package:
        return ""
    if package and name.startswith(f"{package}."):
        return name[len(package) + 1 :]
    return None


def project_module_under_package(
    name: str, names: Collection[str], package: str
) -> Optional[str]:
    """The project module an absolute import ``name`` names: as the modules
    are named (``world``), or under the root package's own name
    (``game.world``); else ``None``."""
    if name in names:
        return name
    rest = strip_package(name, package)
    return rest if rest is not None and rest in names else None


def project_module_by_suffix(written: str, modules: Collection[str]) -> Optional[str]:
    """The project module a ``from <written> import`` names: the module path
    equal to ``written`` or to its tail past a package prefix
    (``space_a.actions`` -> ``actions``), the longest first; else ``None``.
    Unlike ``project_module_under_package`` any prefix is dropped, not only
    the root package's name."""
    parts = written.split(".")
    for start in range(len(parts)):
        tail = ".".join(parts[start:])
        if tail in modules:
            return tail
    return None


__all__ = ["project_module_by_suffix", "project_module_under_package", "strip_package"]
