# DEP001 -- `forbid_imports` showcase

Family #7 of 13. Demonstrates every meaningful axis of `forbid_imports`
using a single module-level marker on `reference/controller.py` and a
matrix of seven targets.

## Marker (one declaration site)

```python
# reference/controller.py
__archtest__: Annotated[
    None,
    forbid_imports(
        "telnetlib",                       # forbidden module
        scope="module",                    # apply to controller's module graph
        mode="reachable",                  # follow imports transitively
        ignore_type_checking=True,         # imports under `if TYPE_CHECKING:` skipped
        allow=("warnings",),               # explicit exception
        ignore_globs=("**/ignored_module.py",),  # files masked from the rule
    ),
]
```

`telnetlib` is the forbidden module (stdlib, deprecated, easy to spot --
won't show up in any helper accidentally). `warnings` is the demonstrated
allow-list exception.

## Reference modules

| Module | Role |
|--------|------|
| `controller.py` | Hosts the single `__archtest__` marker; clean of forbidden imports |
| `helper_clean.py` | Legitimate helper module pulled in by the controller |
| `forbidden_lib.py` | Empty stub that some failing targets repurpose to reach `telnetlib` two hops out |
| `ignored_module.py` | Imports `telnetlib` deliberately; masked by `ignore_globs` |

## Parameter / scenario matrix

| Target | Expected | Concern exercised |
|--------|----------|-------------------|
| `target_pass_basic` | PASS | Baseline -- no forbidden import anywhere |
| `target_pass_allow_exception` | PASS | `import warnings` is in `allow` |
| `target_pass_type_checking_only` | PASS | `import telnetlib` only inside `if TYPE_CHECKING:` -- skipped via `ignore_type_checking=True` |
| `target_pass_ignore_globs` | PASS | `ignored_module` imports `telnetlib` and is reachable from controller, but masked by `ignore_globs` |
| `target_fail_direct_import` | FAIL | controller does `import telnetlib` directly |
| `target_fail_reachable_via_helper` | FAIL | One-hop reachable: `controller -> helper_clean (imports telnetlib)` |
| `target_fail_module_scope` | FAIL | Two-hop reachable: `controller -> helper_clean -> forbidden_lib (imports telnetlib)` |

The two failing reachable targets keep the chain length distinct so the
graph traversal is exercised at depth 1 *and* depth 2.

## Notes on alternate modes

- `mode="direct"` is also supported and would only flag the direct-import
  target; the reachable-via-helper / module-scope targets would silently
  pass. This showcase deliberately uses `mode="reachable"` to exercise
  graph traversal.
- `scope="entity"` is a legacy alias for `scope="module"`; do not use it
  in new declarations.

## How to re-run

The parent harness runs the validation matrix in bulk; do not invoke the
CLI manually for this showcase. For ad-hoc local checks:

```bash
python -m pythonarchtesting.cli \
    --source ./reference \
    --targets-dir ./assignments \
    --format markdown \
    --output ./reports
```

(`reports/` is generated on demand and not checked in.)
