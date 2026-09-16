# API004 — findings

## Expected vs. observed

| Target                                | Expected | Observed                | Status |
|---------------------------------------|----------|-------------------------|--------|
| `target_pass_classmethod_factory`     | PASS     | exit=0, 6 OK            | OK     |
| `target_pass_staticmethod_factory`    | PASS     | exit=0, 6 OK            | OK     |
| `target_pass_constructor_only`        | PASS     | exit=0, 6 OK            | OK     |
| `target_pass_extended_match_by_name`  | PASS     | exit=0, 6 OK            | OK     |
| `target_pass_static_attribute_factory`| PASS     | exit=0, 6 OK            | OK     |
| `target_fail_missing_factory`         | FAIL     | exit=1, 5 OK / 1 FAIL   | OK     |
| `target_fail_wrong_signature`         | FAIL     | exit=1, 5 OK / 1 FAIL   | OK     |
| `target_fail_return_annotation`       | FAIL     | exit=1, 5 OK / 1 FAIL   | OK     |

## Capabilities exercised

- `@classmethod` and `@staticmethod` factories
- `satisfy_with=("constructor",)` accepts plain `__init__`
- `detection_mode="extended"` widens candidate set
- `return_annotation_mode="exact"` enforces precise return-type match
- `aliases=` for canonical factory names
- Static-attribute factory pattern `make = classmethod(_make_impl)` —
  source-side and target-side detection both supported.

## Validation declaration check

`--validate-declarations` reports 0 diagnostics.

## Fix history

### LIMITATION-1 — `make = classmethod(_make_impl)` rejected at compile (fixed)

Previously the reference's `_make_impl` triggered
`compiler_invalid_source_method` ("plain instance methods are not valid
factory sources in v1"), the rule was silently dropped, and every target
in the matrix carried a constant `1 WARNING`.

**Root cause**: source-side AST extraction set `method_kind` only from
direct decorators on the function (`@classmethod` / `@staticmethod`).
A plain `def _make_impl(cls, ...)` paired with `make = classmethod(_make_impl)`
left `method_kind=None`, and `_is_factory_capable_method` rejected it.
Target-side detection (`_declared_assignment_factory_candidates`)
already handled the same pattern — only the source side was missing.

**Fix**: `entities_extraction.ast_extract._propagate_assignment_method_kinds`
walks the `ClassDef` body after entity construction and stamps
`decorators_meta["method_kind"]` (and `extras["assignment_wrapped_by"]`
with the public alias) onto methods wrapped via class-body assignment.
Direct decorators still win when both are present.

Companion changes:
- `factory_resolution.factory_candidates_for_class` excludes methods
  with `assignment_wrapped_by` so the wrapped function does not
  duplicate the synthesized alias.
- `rules.compilation.decorators.factories` auto-elevates the default
  `detection_mode` to `"extended"` when the source has
  `assignment_wrapped_by`, since assignment-wrapped factories are
  inherently an extended-detection pattern.
- `execution.evaluators.api_signature` filters candidates against
  `effective_source_name = source.extras.get("assignment_wrapped_by") or source.name`
  so `name_match="exact"` compares against the public alias (`make`)
  rather than the underlying function (`_make_impl`).

### LIMITATION-2 — default `satisfy_with` admitted `__init__` as a candidate (fixed)

`required_factory(aliases=("make",))` would FAIL with
`multiple_compatible_factory_candidates` whenever the target class had
both the named factory and an `__init__`, because the default
`satisfy_with` was `["constructor", "classmethod", "staticmethod"]`.

**Fix**: in `rules.compilation.decorators.factories`, the default
`satisfy_with` now drops `"constructor"` whenever the caller supplies
any name constraint (`aliases=`, `pattern=`, or `name_match != "any"`).
Bare `required_factory()` still defaults to the broad three-element
list. Callers who explicitly pass `satisfy_with=` are unaffected.

### Parameter discoveries — silent rule drop on invalid enum (fixed)

Invalid `detection_mode` / `return_annotation_mode` values previously
produced only `compiler_invalid_param` evidence and registered no rule.
The dropped rule contributed nothing to `summary.results.status_counts`,
so misconfigured targets reported "all OK" against zero relevant rules.

**Fix**: `rules.compilation.decorators.factories` now emits a sentinel
`Rule(rule_type="compiler_invalid_param", ...)` alongside the evidence
row. A new `CompilerInvalidParamEvaluator` (registered in
`execution.evaluators.registry`) evaluates the sentinel to FAILED, so
the dropped rule is visible in `status_counts` and in the per-target
output instead of silently disappearing.

Valid parameter values (unchanged):
- `detection_mode`: `"extended"`, `"strict"`
- `return_annotation_mode`: `"compatible"`, `"exact"`, `"ignore"`
