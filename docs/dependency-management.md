# Dependency Management

`pyproject.toml` is the only authoritative source for dependency declarations in
this repository.

## Files

- `pyproject.toml`: runtime dependencies, development extras, and tool
  configuration

## Install dependencies

Preferred runtime install:

```powershell
pip install .
```

Optional MCP server (adds `mcp>=2.3,<3` and the `python-arch-test-mcp`
command, see [mcp.md](mcp.md)):

```powershell
pip install ".[mcp]"
```

Editable install with dev extras (these include the `mcp` extra):

```powershell
pip install -e .[dev]
```

## Editing dependencies

Edit dependencies only in `pyproject.toml`:

- `[project.dependencies]` for runtime requirements: `typing-extensions`, and
  `tomli` on Python 3.10 only (the principle catalogue is TOML; 3.11 has
  `tomllib`)
- `[project.optional-dependencies].mcp` for the MCP server
- `[project.optional-dependencies].eval` (`import-linter`) for the baseline of
  the architectural-mutant evaluation
  (`example/architectural_mutants/baselines/importlinter.py`), installed with
  `pip install ".[eval]"`
- `[project.optional-dependencies].dev` for development, test, and documentation
  tooling; it repeats the `mcp` requirement so the MCP tests run

`docs/markers/*.md` are also installed as data files under
`share/pythonarchtesting/markers`, which is where the MCP server reads the
marker catalogue when it does not run from a checkout.

CI installs from package metadata with `python -m pip install .[dev]`. Plain
requirements files are not part of the supported repository workflow.
