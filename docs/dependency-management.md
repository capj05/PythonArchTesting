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

Editable install with dev extras:

```powershell
pip install -e .[dev]
```

## Editing dependencies

Edit dependencies only in `pyproject.toml`:

- `[project.dependencies]` for runtime requirements
- `[project.optional-dependencies].dev` for development, test, and documentation
  tooling

CI installs from package metadata with `python -m pip install .[dev]`. Plain
requirements files are not part of the supported repository workflow.
