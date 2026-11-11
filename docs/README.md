# Documentation

Read these in order on first contact with the tool. Each entry is one short
purpose-line.

## Teaching

1. [mcp.md](mcp.md) — the MCP server a teacher's AI client drives: the
   teaching workflow, the principle catalogue, results by typical error, and
   every tool
2. [tasks.md](tasks.md) — a teaching task: a catalogue principle bound to an
   unannotated reference by `task.toml`
3. [../example/principles/README.md](../example/principles/README.md) — one
   worked task per principle, with variants for each typical error
4. [global_mode.md](global_mode.md) — principles checked in a student's
   free-form project without a model solution: `discover_roles`,
   `prepare_global_task`, `run_global_evaluation`
5. [dynamic-checks.md](dynamic-checks.md) — how the principle's checks run the
   submissions, what a pass means, and the sandbox
6. [reporting.md](reporting.md) — JSON and Markdown output, statuses, and exit
   codes
7. [configuration.md](configuration.md) — `.pythonarchtesting` reference

## Advanced: markers and architecture checks

8. [overview.md](overview.md) — concepts, supported checks, and what the tool
   does not do
9. [usage-guide.md](usage-guide.md) — step-by-step worked example using
   `example/checkout_assignment/`, and every CLI flag
10. [api-reference.md](api-reference.md) — every marker and its full option
    surface
11. [markers/README.md](markers/README.md) — per-marker quick reference, one
    page per marker
12. [pattern-recipes.md](pattern-recipes.md) — ready-to-use marker
    combinations for common patterns
13. [architecture.md](architecture.md) — pipeline, module map, and extension
    points

## Contributors

14. [testing.md](testing.md) — running tests and quality gates
15. [dependency-management.md](dependency-management.md) — dependency policy
