# DEP001 — findings

## Expected vs. observed

| Target                              | Expected | Observed              | Status |
|-------------------------------------|----------|-----------------------|--------|
| `target_pass_basic`                 | PASS     | exit=0, 1 OK          | OK     |
| `target_pass_allow_exception`       | PASS     | exit=0, 1 OK          | OK     |
| `target_pass_type_checking_only`    | PASS     | exit=0, 1 OK          | OK     |
| `target_pass_ignore_globs`          | PASS     | exit=0, 1 OK          | OK     |
| `target_fail_direct_import`         | FAIL     | exit=1, 1 FAIL        | OK     |
| `target_fail_module_scope`          | FAIL     | exit=1, 1 FAIL        | OK     |
| `target_fail_reachable_via_helper`  | FAIL     | exit=1, 1 FAIL        | OK     |

## Defects observed

### DEFECT-1 — `ignore_globs` does NOT prevent intermediate hops in reachable mode (FIXED)

Originally observed: the reference declared
`forbid_imports("telnetlib", ignore_globs=("**/ignored_module.py",))` in
reachable mode, but the target FAILed with the path
`controller → ignored_module → telnetlib`.

Two bugs caused this:

1. The glob matcher used `fnmatch.fnmatch`, which is shell-style and
   path-unaware: `**/ignored_module.py` did not match a top-level
   `ignored_module.py` because the literal `/` in the pattern still
   required a `/` in the input. Fixed by introducing
   `pythonarchtesting.execution.glob_match.path_matches_any_glob` with
   gitignore-style `**` semantics (zero or more path segments) and wiring
   it into both `import_edges` and the `import_policy` evaluator.
2. The annotation-declaration compiler in
   `rules.compilation.decorators.import_policy` only accepted `list`
   sequences for `forbidden`, `allow`, and `ignore_globs`. Annotation
   declarations use tuple literals (e.g. `("**/ignored_module.py",)`),
   which `ast.literal_eval` returns as Python tuples; these were
   silently dropped to empty lists. Fixed by accepting `(list, tuple)`.

After both fixes, `controller → ignored_module → ...` stops at the
externalized `ignored_module` node and the rule PASSes.

## Capabilities exercised

- `mode="direct"` (AST-only direct-import check).
- `mode="reachable"` (default) — graph reachability through transitive imports.
- `scope="module"` and `scope="package"` — package scope catches imports
  anywhere in the package, not just the declaring module.
- `allow=` exception list (passes when the listed module is the only
  target).
- `if TYPE_CHECKING:` imports are ignored by both modes.

## Validation declaration check

`--validate-declarations` reports 0 diagnostics.
