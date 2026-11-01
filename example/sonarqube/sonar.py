"""SonarQube Server's architecture analysis on the architectural mutants (T6, E5).

SonarQube's intended architecture (2026.4+) is a set of containers and the
relations allowed between siblings; any other dependency between siblings is
a deviation, raised as an issue. It needs a commercial edition, so this script
runs the Developer edition locally (``127.0.0.1`` only) with a trial licence.

Steps, from the repository root (``docker`` must be available)::

    python example/sonarqube/sonar.py up        # start the server
    SONAR_LICENSE=... python example/sonarqube/sonar.py init
    python example/sonarqube/sonar.py plan      # intended-architecture.md
    python example/sonarqube/sonar.py scan --base
    # enter the intended architecture of each project in the UI, by plan
    python example/sonarqube/sonar.py scan      # every variant, as a branch
    python example/sonarqube/sonar.py collect   # results.md, results.csv
    python example/sonarqube/sonar.py down      # remove the container

The intended architecture is derived from the reference's ``enforce_layers``
marker, as the import-linter contracts of E5 are: a layer may depend on the
layers below it, not past a closed one; modules of one layer (``a | b``) are
independent; a module in no layer is unconstrained. SonarQube documents no
file format or Web API for it (only the UI), so ``plan`` writes what to enter.

Each program is one project; the unchanged solution is its main branch and
every mutant and equivalent rewrite (hand-written and held-out) a branch of
it, so that the intended architecture is entered once per program. A variant
counts as *caught* when its branch has an issue of an architecture rule the
main branch does not have.

Secrets: the licence comes only from ``SONAR_LICENSE``; the admin password
and the analysis token ``init`` makes live in ``.state/server.json`` (mode
600, git-ignored) and are never printed. The scanner gets the token through
its environment, not its command line.
"""

from __future__ import annotations

import argparse
import base64
import csv
import json
import os
import secrets
import shutil
import string
import subprocess  # nosec B404 - runs docker with fixed arguments
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
EXAMPLES = HERE.parent
sys.path.insert(0, str(EXAMPLES / "architectural_mutants"))

from run import _apply, _variants  # noqa: E402  (the mutant harness's own helpers)

PROGRAMS = {
    "program1": EXAMPLES / "architectural_mutants",
    "program2": EXAMPLES / "architectural_mutants_2",
    "program3": EXAMPLES / "architectural_mutants_3",
}
URL = "http://127.0.0.1:9000"
CONTAINER = "pat-sonarqube"
IMAGE = "sonarqube:developer"
SCANNER = "sonarsource/sonar-scanner-cli:latest"
STATE = HERE / ".state"
WORK = STATE / "work"
SECRETS = STATE / "server.json"


# --- server -----------------------------------------------------------------


def _docker(*args: str, env: dict[str, str] | None = None) -> None:
    subprocess.run(["docker", *args], check=True, env=env)  # nosec B603 B607


def _state() -> dict[str, str]:
    if not SECRETS.is_file():
        raise SystemExit("run `init` first")
    state: dict[str, str] = json.loads(SECRETS.read_text(encoding="utf-8"))
    return state


def _call(
    method: str,
    path: str,
    params: dict[str, str] | None = None,
    auth: tuple[str, str] | None = None,
) -> Any:
    """One Web API call; ``auth`` is (login, password) or (token, "")."""
    data = urllib.parse.urlencode(params or {})
    url = f"{URL}/{path}" + (f"?{data}" if method == "GET" and data else "")
    request = urllib.request.Request(
        url, data=data.encode() if method == "POST" else None, method=method
    )
    if auth is None and SECRETS.is_file():
        auth = (_state()["token"], "")
    if auth is not None:
        pair = base64.b64encode(f"{auth[0]}:{auth[1]}".encode()).decode()
        request.add_header("Authorization", f"Basic {pair}")
    try:
        with urllib.request.urlopen(request, timeout=60) as response:  # nosec B310
            body = response.read()
    except urllib.error.HTTPError as exc:
        # The body names the problem; it never holds a secret we sent.
        raise SystemExit(f"{method} {path}: HTTP {exc.code}: {exc.read()[:300]!r}")
    return json.loads(body) if body.strip() else {}


def up(args: argparse.Namespace) -> None:
    _docker(
        "run", "-d", "--name", CONTAINER, "-p", "127.0.0.1:9000:9000",
        "--memory", "3g", IMAGE,
    )  # fmt: skip
    for _ in range(120):
        try:
            if _call("GET", "api/system/status", auth=("", "")).get("status") == "UP":
                print("server up at", URL)
                return
        except (SystemExit, OSError):
            pass
        time.sleep(5)
    raise SystemExit("the server did not come up in 10 minutes")


def _password() -> str:
    alphabet = string.ascii_letters + string.digits
    core = "".join(secrets.choice(alphabet) for _ in range(20))
    return core + "aA1!"  # the server wants every character class


def init(_: argparse.Namespace) -> None:
    licence = os.environ.get("SONAR_LICENSE")
    if not licence:
        raise SystemExit("set SONAR_LICENSE to the trial licence key")
    STATE.mkdir(exist_ok=True)
    password = _password()
    _call(
        "POST",
        "api/users/change_password",
        {"login": "admin", "previousPassword": "admin", "password": password},
        auth=("admin", "admin"),
    )
    admin = ("admin", password)
    _call("POST", "api/editions/set_license", {"license": licence}, auth=admin)
    valid = _call("GET", "api/editions/is_valid_license", auth=admin)
    token = _call("POST", "api/user_tokens/generate", {"name": "pat-e5"}, auth=admin)[
        "token"
    ]
    SECRETS.write_text(json.dumps({"password": password, "token": token}))
    SECRETS.chmod(0o600)
    print("licence valid:", valid.get("isValidLicense"))


def down(_: argparse.Namespace) -> None:
    _docker("rm", "-f", CONTAINER)


# --- the intended architecture --------------------------------------------


def _layers(program: Path) -> tuple[list[list[str]], set[str], list[str]]:
    """The reference's layers (top first, each a list of modules), the closed
    layers' modules, and the program's top-level modules and packages."""
    from pythonarchtesting.config import load_config
    from pythonarchtesting.runner.source_prep import prepare_source

    state = prepare_source(
        config=load_config(cli_args={}, discover_from_cwd=False),
        source_path=(program / "reference").resolve(),
    )
    rule = next(
        r
        for r in state.rules
        if "enforce_layers" in r.rule_id and r.evidence_type != "runtime"
    )
    layers = [
        [part.strip() for part in str(layer).split("|")]
        for layer in rule.params["layers"]
    ]
    solution = program / "solution"
    top = sorted(
        path.stem if path.is_file() else path.name
        for path in solution.iterdir()
        if (path.suffix == ".py" and path.stem != "__init__")
        or (path.is_dir() and (path / "__init__.py").is_file())
    )
    return layers, set(rule.params.get("closed") or []), top


def _allowed(layers: list[list[str]], closed: set[str]) -> list[tuple[str, str]]:
    allowed = []
    for upper, modules in enumerate(layers):
        for lower in range(upper + 1, len(layers)):
            between = {m for layer in layers[upper + 1 : lower] for m in layer}
            if between & closed:
                break  # a closed layer may not be skipped
            allowed += [(a, b) for a in modules for b in layers[lower]]
    return allowed


def plan(_: argparse.Namespace) -> None:
    lines = [
        "# Intended architecture to enter in SonarQube",
        "",
        "Generated by `sonar.py plan` from each reference's `enforce_layers`.",
        "For each project: Architecture > Intended architecture; add the",
        "containers below as top-level containers (a module is its `.py` file,",
        "a package its directory, under `src/`), then the allowed relations",
        "between them, and Save. Every other relation between these siblings",
        "is forbidden. Containers in no layer are left out (unconstrained).",
        "",
    ]
    for name, program in PROGRAMS.items():
        layers, closed, top = _layers(program)
        layered = [m for layer in layers for m in layer]
        lines += [
            f"## Project `pat-{name}`",
            "",
            "Layers, top first: "
            + " > ".join(" | ".join(layer) for layer in layers)
            + (f" (closed: {', '.join(sorted(closed))})" if closed else ""),
            "",
            "Containers: " + ", ".join(f"`{m}`" for m in layered),
            "",
            f"Left out: {', '.join(m for m in top if m not in layered) or 'none'}",
            "",
            "Allowed relations:",
            "",
        ]
        lines += [f"- `{a}` -> `{b}`" for a, b in _allowed(layers, closed)]
        lines.append("")
    (HERE / "intended-architecture.md").write_text("\n".join(lines), encoding="utf-8")
    print("wrote", HERE / "intended-architecture.md")


# --- analysis -----------------------------------------------------------------


def _all_variants(program: Path) -> list[dict[str, Any]]:
    found = []
    for label, path in (("hand", None), ("held-out", program / "llm_mutants.py")):
        for variant in _variants(program, path):
            kind = "mutant" if variant["id"].startswith("M") else "equivalent"
            found.append({**variant, "set": label, "kind": kind})
    return found


def _scan(project: str, root: Path, branch: str | None) -> None:
    env = {**os.environ, "SONAR_TOKEN": _state()["token"]}
    _docker(
        "run", "--rm", "--network", "host", "-e", "SONAR_TOKEN",
        "-e", f"SONAR_HOST_URL={URL}", "-v", f"{root}:/usr/src", SCANNER,
        f"-Dsonar.projectKey={project}", "-Dsonar.sources=src",
        "-Dsonar.python.version=3.12", "-Dsonar.qualitygate.wait=true",
        *([f"-Dsonar.branch.name={branch}"] if branch else []),
        env=env,
    )  # fmt: skip


def _copy(program: Path, variant: dict[str, Any] | None, root: Path) -> None:
    if root.exists():
        shutil.rmtree(root)
    shutil.copytree(
        program / "solution", root / "src", ignore=shutil.ignore_patterns("__pycache__")
    )
    if variant is not None:
        _apply(variant, root / "src")


def scan(args: argparse.Namespace) -> None:
    wanted = set(args.only.split(",")) if args.only else None
    for name, program in PROGRAMS.items():
        if args.program and name != args.program:
            continue
        project = f"pat-{name}"
        if args.base:
            try:
                _call(
                    "POST", "api/projects/create", {"project": project, "name": project}
                )
            except SystemExit as exc:
                if "already exists" not in str(exc):
                    raise
            root = WORK / name / "main"
            _copy(program, None, root)
            _scan(project, root, None)
            continue
        for variant in _all_variants(program):
            branch = f"{variant['set']}-{variant['id']}"
            if wanted and variant["id"] not in wanted:
                continue
            root = WORK / name / branch
            _copy(program, variant, root)
            _scan(project, root, branch)


def _issues(project: str, branch: str | None) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    page = 1
    while True:
        params = {"componentKeys": project, "ps": "500", "p": str(page)}
        if branch:
            params["branch"] = branch
        found = _call("GET", "api/issues/search", params)
        issues += found.get("issues", [])
        if page * 500 >= int(found.get("paging", {}).get("total", 0)):
            return issues
        page += 1


def _key(issue: dict[str, Any]) -> tuple[str, str, str]:
    component = str(issue.get("component", "")).split(":", 1)[-1]
    return str(issue.get("rule")), component, str(issue.get("message"))


def _architectural(issue: dict[str, Any]) -> bool:
    # The rule keys of deviations are not documented; the raw issues are
    # kept per branch (issues/) to check this filter against what came back.
    return "architecture" in str(issue.get("rule", "")).lower()


def collect(_: argparse.Namespace) -> None:
    raw = STATE / "issues"
    raw.mkdir(parents=True, exist_ok=True)
    rows = []
    for name, program in PROGRAMS.items():
        project = f"pat-{name}"
        base = {_key(i) for i in _issues(project, None) if _architectural(i)}
        for variant in _all_variants(program):
            branch = f"{variant['set']}-{variant['id']}"
            issues = _issues(project, branch)
            (raw / f"{project}-{branch}.json").write_text(json.dumps(issues, indent=1))
            new = sorted({_key(i) for i in issues if _architectural(i)} - base, key=str)
            rows.append(
                {
                    "program": name,
                    "set": variant["set"],
                    "variant": variant["id"],
                    "kind": variant["kind"],
                    "operator": variant.get("operator", ""),
                    "flagged": int(bool(new)),
                    "issues": "; ".join(f"{r} {c}: {m}" for r, c, m in new),
                }
            )
    with (HERE / "results.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    lines = [
        "# SonarQube architecture analysis on the architectural mutants",
        "",
        "Generated by `sonar.py collect`; do not edit by hand.",
        "",
        "| Program | Set | Mutants flagged | Equivalents flagged (FP) |",
        "|---|---|---|---|",
    ]
    for name in PROGRAMS:
        for label in ("hand", "held-out"):
            mine = [r for r in rows if r["program"] == name and r["set"] == label]
            mutants = [r for r in mine if r["kind"] == "mutant"]
            equivalents = [r for r in mine if r["kind"] == "equivalent"]
            lines.append(
                f"| {name} | {label} | {sum(r['flagged'] for r in mutants)}/"
                f"{len(mutants)} | {sum(r['flagged'] for r in equivalents)}/"
                f"{len(equivalents)} |"
            )
    (HERE / "results.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("wrote", HERE / "results.md", "and", HERE / "results.csv")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    for name, handler in (("up", up), ("init", init), ("plan", plan), ("down", down)):
        commands.add_parser(name).set_defaults(handler=handler)
    scanning = commands.add_parser("scan")
    scanning.add_argument("--base", action="store_true", help="main branches only")
    scanning.add_argument("--program", choices=sorted(PROGRAMS))
    scanning.add_argument("--only", help="comma-separated variant ids")
    scanning.set_defaults(handler=scan)
    commands.add_parser("collect").set_defaults(handler=collect)
    args = parser.parse_args()
    args.handler(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
