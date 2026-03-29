# Configuration

Configuration is INI-based and validated against the supported schema.

## Supported Sections

- `[discovery]`
- `[type_check]`
- `[import]`
- `[logging]`
- `[error_handling]`
- `[files]`
- `[performance]`
- `[memory]`
- `[reporting]`
- `[matching]`
- `[output]`
- `[report]`
- `[reference]`
- `[projects]`

## Removed Sections

These sections are no longer accepted:

- `[arch_rules]`
- `[runtime]`
- `[structural_check]`

If either section appears in a config file, configuration loading fails with an unknown-section validation error.

## Example

```ini
[discovery]
included_file_patterns = *.py

[type_check]
enabled = true
strict = true
check_arguments = true
check_return_values = true
show_annotation_warnings = true

[report]
include_config_snapshot = true
validate_schema_v2 = true
```

## Stub-Only Reference Projects

Use a dedicated `.pyi` reference tree when you want declaration-only source files:

```ini
[discovery]
included_file_patterns = *.pyi
include_init_files = true
```

Notes:

- This affects source/reference discovery, including declaration validation and source-side module resolution for `--reference-modules`.
- `.pyi` package files such as `pkg/__init__.pyi` are supported.
- Mixed `.py` and `.pyi` siblings for the same reference module are intentionally out of scope in v1; prefer one style per reference tree.
