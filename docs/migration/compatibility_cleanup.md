# Compatibility Cleanup Migration

Use the canonical public modules directly.

## Mapping

- `pythonarchtesting.state.state.*` -> `pythonarchtesting.state.*`
- `pythonarchtesting.runner_multi.*` -> removed; use `pythonarchtesting.runner.*`
- `pythonarchtesting.state.project_state.ProjectState` -> `pythonarchtesting.state.ProjectState`
- `ProjectState.get("x")` -> `ProjectState.x`
- `ProjectState.get("x", default)` -> `getattr(ProjectState, "x", default)`
