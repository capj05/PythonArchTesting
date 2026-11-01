"""import-linter as a baseline: the reference's import markers as contracts.

Every import marker of the reference becomes one contract of import-linter
(https://import-linter.readthedocs.io), so both tools check the same intents
and the evaluation can compare them on the same variants:

- ``forbid_imports`` becomes a ``forbidden`` contract. ``mode="direct"`` maps
  to ``allow_indirect_imports = True``; the default ``mode="reachable"`` to
  import-linter's default, which also forbids indirect chains.
- ``enforce_layers`` becomes a ``layers`` contract with the same layers.
  import-linter 2.15 cannot declare a closed layer in its configuration, so
  ``closed`` has no counterpart there.
- ``forbid_cycles`` becomes an ``acyclic_siblings`` contract on the package:
  in a package of plain modules, its siblings are the modules.
 import-linter reads every import statement, including those
inside functions, and has no entity matching: a contract names the
reference's modules, so a target that renamed one is checked under the old
name.

The generated contracts and the outcome of a check are named after the marker
and the module that declares it (``forbid_imports-controller``,
``enforce_layers-root`` for the root package), so a broken contract counts
for the intent of the marker it came from.
"""

from __future__ import annotations

import re
import subprocess  # nosec B404 - runs the import-linter CLI on a local copy
import sys
from pathlib import Path

from pythonarchtesting.config.loader import load_config
from pythonarchtesting.runner.source_prep import prepare_source

_LINE = re.compile(r"^(?P<name>\S+) (?P<state>KEPT|BROKEN)$")


def contract_marker(contract: str) -> str:
    """``forbid_imports-controller`` -> ``forbid_imports``."""
    return contract.split("-", 1)[0]


def contracts(reference: Path, package: str) -> str:
    """The ``.importlinter`` text for the markers of ``reference``.

    ``package`` is the name the target is imported as; the reference's own
    modules are named inside it, everything else (``sqlite3``) is external.
    """
    state = prepare_source(config=load_config(), source_path=reference.resolve())
    own = {path.stem for path in reference.glob("*.py")}
    sections = [
        "[importlinter]",
        f"root_package = {package}",
        "include_external_packages = True",
    ]
    for rule in state.rules:
        if rule.evidence_type != "static":
            continue
        entity = state.source_by_id[rule.selector.source_entity_id]
        name = f"{rule.name}-{entity.module_path or 'root'}"
        if rule.name == "enforce_layers":
            sections += [
                "",
                f"[importlinter:contract:{name}]",
                f"name = {name}",
                "type = layers",
                f"containers = {package}",
                "layers =",
                *(f"    {layer}" for layer in rule.params["layers"]),
            ]
            continue
        if rule.name == "forbid_cycles":
            sections += [
                "",
                f"[importlinter:contract:{name}]",
                f"name = {name}",
                "type = acyclic_siblings",
                f"ancestors = {package}",
            ]
            continue
        if rule.name != "forbid_imports":
            continue
        forbidden = [
            f"{package}.{module}" if module in own else module
            for module in rule.params["forbidden"]
        ]
        sections += [
            "",
            f"[importlinter:contract:{name}]",
            f"name = {name}",
            "type = forbidden",
            f"source_modules = {package}.{entity.module_path}",
            "forbidden_modules =",
            *(f"    {module}" for module in forbidden),
        ]
        if rule.params.get("mode") == "direct":
            sections.append("allow_indirect_imports = True")
    return "\n".join(sections) + "\n"


def check(target: Path, config: Path) -> tuple[list[str], str]:
    """Contracts ``target`` breaks, and the error text if the check failed.

    ``target`` is the package directory; import-linter imports it from its
    parent directory.
    """
    lint = Path(sys.executable).with_name("lint-imports")
    if not lint.exists():
        return [], "import-linter is not installed"
    completed = subprocess.run(  # nosec B603 - fixed argument list
        [str(lint), "--config", str(config), "--no-cache", "--no-logo"],
        cwd=target.parent,
        capture_output=True,
        text=True,
        check=False,
    )
    states = {
        match["name"]: match["state"]
        for match in map(_LINE.match, completed.stdout.splitlines())
        if match
    }
    if completed.returncode not in (0, 1) or not states:
        return [], (completed.stderr or completed.stdout)[-2000:]
    return sorted(name for name, state in states.items() if state == "BROKEN"), ""
