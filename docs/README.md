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
4. [dynamic-checks.md](dynamic-checks.md) — how the principle's checks run the
   submissions, what a pass means, and the sandbox
5. [reporting.md](reporting.md) — JSON and Markdown output, statuses, and exit
   codes
6. [configuration.md](configuration.md) — `.pythonarchtesting` reference

## Advanced: markers and architecture checks

7. [overview.md](overview.md) — concepts, supported checks, and what the tool
   does not do
8. [usage-guide.md](usage-guide.md) — step-by-step worked example using
   `example/checkout_assignment/`
9. [api-reference.md](api-reference.md) — every marker and its full option
   surface
10. [markers/README.md](markers/README.md) — per-marker quick reference, one
    page per marker
11. [pattern-recipes.md](pattern-recipes.md) — ready-to-use marker
    combinations for common patterns
12. [architecture.md](architecture.md) — pipeline, module map, and extension
    points

## Contributors

13. [testing.md](testing.md) — running tests and quality gates
14. [dependency-management.md](dependency-management.md) — dependency policy
