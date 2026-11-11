# Configuration

Configuration is INI-based. For most users, the important settings are the ones
that choose the reference and targets, shape discovery, tune matching, and
control the report and exit code.

The bundled default configuration is always loaded internally from the package.
For normal CLI usage, when `--config` is omitted, the CLI enables config
auto-discovery in this order:

1. explicit `--config path/to/file.conf`
2. auto-discovered `.pythonarchtesting` from the current working directory

The [MCP server](mcp.md) never uses the working directory: it loads an
explicit `config`, else `.pythonarchtesting` in `source` or its parent, and
never `PYTHON_ARCH_TARGET_PATH`.

CLI arguments remain the highest-priority overrides after file loading.
Environment-variable overlays are not supported by `load_config()`. The one
environment variable the CLI reads is `PYTHON_ARCH_TARGET_PATH`: a single
target, used only when neither the flags nor `[projects]` name any.

Point the CLI at a custom file when you need an explicit override:

```bash
python-arch-test --config path/to/custom.conf ...
```

Nullable config fields use the literal token `null` in INI files. For example,
`[logging] output_file = null` clears the deprecated alias and leaves
`logging.filename` as the canonical setting.

## Common Sections

### `[projects]`

Use this section when you want defaults for repeated runs.

Common fields:

- `source_path`
- `target_path`
- `targets`
- `targets_dir`
- `project_pattern`
- `exclude_patterns`

### `[discovery]`

Controls which files are scanned.

Common fields:

- `included_file_patterns`
- `include_init_files`
- `excluded_dirs`
- `follow_symlinks`
- `exclude_hidden_dirs` (default `true`): skip directories starting with `.`
- `max_discovery_depth` (default `-1`, unlimited)

Stub-only reference projects can opt into `.pyi` discovery:

```ini
[discovery]
included_file_patterns = *.pyi
include_init_files = true
```

### `[matching]`

Controls how source entities are paired with target entities.

Common fields:

- `threshold`
- `delta`
- `min_candidate`
- `top_n`
- `max_fuzzy_candidates`
- `name_fallback` (default `true`): pair by name what the scores leave
  unpaired, see [reporting.md](reporting.md#pairing-by-name)
- `max_stage2_candidates`, `max_stage3_candidates` (default `0`)
- `include_nested_functions` (default `false`): also extract functions
  nested in other functions

Most users should keep the defaults unless matching is too strict or too loose
for their project layout.

### `[report]`

Controls exit behavior and report payload options.

Common fields:

- `warnings_as_fail`
- `run_exit_policy`
- `fail_threshold`
- `include_config_snapshot`
- `validate_schema_v2`
- `schema_version` (only `2`)
- `max_evidence_items_text` (default `3`)
- `markdown_detail` (`summary`, `verbose` default, `debug`; see
  [reporting.md](reporting.md#detail-level))

`run_exit_policy` supports:

- `any_fail`: the run fails if any target fails
- `all_fail`: the run fails only if every target fails
- `threshold`: the run fails when failed targets reach `fail_threshold`

## Example

```ini
[projects]
source_path = example/checkout_assignment/reference
targets_dir = example/checkout_assignment/assignments
project_pattern = target*

[discovery]
included_file_patterns = *.py
include_init_files = true

[matching]
threshold = 0.80
delta = 0.03

[report]
warnings_as_fail = false
run_exit_policy = any_fail
include_config_snapshot = false
```

## Advanced Sections

This section is part of the supported schema but is usually secondary for
user onboarding:

- `[logging]`: `level` (default `WARNING`), `file` (default `false`: also log
  to a file), `filename` (default `log.txt`), `output_file` (deprecated alias
  of `filename`)

## Removed Sections

- `[arch_rules]`, `[runtime]`, `[structural_check]`, and `[type_check]` are no
  longer supported. Validation now fails if one appears in a user config file.
- `[import]`, `[error_handling]`, `[files]`, `[performance]`, `[reporting]`, and
  `[memory]` were removed because nothing read them, together with
  `discovery.auto_discover` and `projects.required_modules`. A config that still
  sets them loads normally; each one produces an "unknown configuration
  section" or "unknown configuration key" warning and is ignored.
  The report format is chosen with `--format`.

Runtime checks have no config section: `--dynamic`, `--sandbox`,
`--sandbox-memory-mb`, and the arguments of the runtime markers control them.
