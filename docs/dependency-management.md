# Dependency Management

This project uses package installation for normal CLI usage and keeps two plain
requirements files for dependency management:

- `requirements.txt` for runtime dependencies
- `requirements-dev.txt` for optional development, test, and documentation dependencies

## Files

- `requirements.txt`: user/runtime dependencies
- `requirements-dev.txt`: optional developer tooling, tests, and docs dependencies
- `pyproject.toml`: package metadata plus matching `dev` extras for editable installs

## Install dependencies

Preferred runtime install:

```powershell
pip install .
```

Runtime dependencies only:

```powershell
pip install -r requirements.txt
```

Development tools only:

```powershell
pip install -r requirements-dev.txt
```

Editable install with dev extras:

```powershell
pip install -e .[dev]
```

The requirements files are intentionally maintained without hashes so they stay easy to read and update.
