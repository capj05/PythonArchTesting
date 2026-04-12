# Configuration

Configuration is INI-based. For most users, the important settings are the ones
that choose the reference and targets, shape discovery, tune matching, and
control reporting.

The bundled default configuration is always loaded internally from the package.
For normal CLI usage, when `--config` is omitted, the CLI enables config
auto-discovery in this order:

1. explicit `--config path/to/file.conf`
2. auto-discovered `.pythonarchtesting` from the current working directory

CLI arguments remain the highest-priority overrides after file loading.
Environment-variable overlays are not supported by `load_config()`.

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

Most users should keep the defaults unless matching is too strict or too loose
for their project layout.

### `[reporting]`

Controls the output formats and detail level.

Common fields:

- `output_formats`
- `error_detail_level`
- `include_traceback`

### `[report]`

Controls exit behavior and report payload options.

Common fields:

- `warnings_as_fail`
- `multi_target_exit_policy`
- `fail_threshold`
- `include_config_snapshot`
- `validate_schema_v2`

`multi_target_exit_policy` supports:

- `any_fail`: the run fails if any target fails
- `all_fail`: the run fails only if every target fails
- `threshold`: the run fails when failed targets reach `fail_threshold`

## Example

```ini
[projects]
source_path = path/to/reference
targets_dir = path/to/assignments
project_pattern = target*

[discovery]
included_file_patterns = *.py
include_init_files = true

[matching]
threshold = 0.80
delta = 0.03

[reporting]
output_formats = json, markdown
error_detail_level = standard

[report]
warnings_as_fail = false
multi_target_exit_policy = any_fail
include_config_snapshot = false
```

## Advanced Sections

These sections are part of the supported schema but are usually secondary for
user onboarding:

- `[import]`
- `[logging]`
- `[error_handling]`
- `[files]`
- `[performance]`
- `[memory]`

## Removed Sections

- `[type_check]` is no longer supported. Validation now fails if it appears in
  a user config file.
