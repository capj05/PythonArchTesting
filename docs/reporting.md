# Reporting System

## Overview

Reporting uses dispatcher-based lazy loading. The selected sink is resolved in
`src/report/dispatcher.py`, and only that generator module is imported.

This keeps CLI startup lightweight and makes the supported reporting surface
small and explicit.

## Core Components

1. Dispatcher: `src/report/dispatcher.py`
2. Typed IR: `src/report/ir/`
3. Rendering primitives: `src/report/renderers/`
4. API facade: `src/report/api.py`
5. Core compatibility shim: `src/report/core.py`
6. Lazy wrapper module: `src/report/lazy.py`

## Sink Registry

`src/report/dispatcher.py` defines `_SINK_REGISTRY`:

- `json`
- `markdown`

Each entry maps sink name -> `(module_path, class_name)`.

## Runtime Flow

1. `src/report/api.py` is the canonical report ownership boundary.
2. API builds typed IR from execution state via `src/report/ir/from_state.py`.
3. IR is serialized to schema-v2 payload (`src/report/ir/serialize.py`) for compatibility.
4. `create_reporter(sink, report_data, **kwargs)` imports only the sink module.
5. Sink classes use shared renderer utilities from `src/report/renderers/`.

## Public Reporting Functions

From `src/report/api.py`:

- `build_report(state_obj, config=None) -> dict`
- `generate_validation_report(state_obj, output_format="json", ...) -> str`
- `build_multi_target_report(run_state, target_states, config=None) -> dict`
- `generate_multi_target_report(run_state, target_states, output_format="json", ...) -> str`
- `get_multi_exit_code(run_state, target_states, config=None) -> int`

Supported sinks are:

- `json` (single artifact or stdout)
- `markdown` (directory bundle with `report.md` + `targets/*.md`)

`src/report/lazy.py` provides lazy wrappers with the same surface for CLI usage.

## Extending with a New Sink

1. Implement a new generator class deriving from `BaseReportGenerator`.
2. Add sink mapping to `_SINK_REGISTRY` in `src/report/dispatcher.py`.
3. Use the sink via CLI `--format <name>` or `create_reporter("<name>", ...)`.

## Notes

- There is no `src/report/registry.py`; dispatcher is the active extension point.
- `src/report/core.py` is a compatibility wrapper that delegates to `src/report/api.py`.
- `src/report/api.py` delegates format-specific rendering to dispatcher sinks.
- For multi-target `markdown`, CLI `--output` must point to an output directory.
