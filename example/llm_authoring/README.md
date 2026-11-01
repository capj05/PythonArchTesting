# Markers written by an LLM, with and without the checking tools (E4)

Does an LLM write better markers when it can check them with `check_cases`
and `verify_marker` (F4.2, F4.3)? Agents (Claude Sonnet) get a copy of a
program's correct solution without markers (`<program>/<condition>-<run>/
reference`), the assignment's graded architecture
(`../llm_solutions/<program>/assignment.md`) and the marker documentation,
and write markers for every requirement.

- condition **A**: `tools.py validate` and `tools.py evaluate` (the correct
  solution must pass);
- condition **B**: also `tools.py check-cases` and `tools.py verify-marker`.

Two runs per program and condition. The agents were told to read only the
assignment, the solution, their reference and `docs/markers`,
`docs/dynamic-checks.md`, `docs/api-reference.md` — not the authors'
reference, the mutants or any results. `tools.py` gives them the MCP tools
from a shell. `score.py` runs every written reference (and the authors' own,
for scale) through the hand-written mutants and equivalents of the program
and writes `results.md`.
