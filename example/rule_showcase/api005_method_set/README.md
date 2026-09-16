# API005 — `require_method_set` showcase

Reference module declares one `require_method_set` marker per class so that
each target isolates a single concern (counting bounds, name-match strategy,
declared-only enforcement, or method-kind constraint).

## Marker matrix exercised

| Reference class       | `name_match` | `names` / `pattern`                    | `method_kind` | `declared_only` | `min_count` | `max_count` |
|-----------------------|--------------|----------------------------------------|---------------|-----------------|-------------|-------------|
| `HandlerSet`          | regex        | `^handle_.*$`                          | any           | False           | 2           | 5           |
| `AliasMethods`        | alias        | `("validate", "check", "verify")`      | any           | False           | 1           | 1           |
| `ClassmethodFactories`| alias        | `("create", "build", "make")`          | class         | False           | 1           | None        |
| `DeclaredHandlers`    | regex        | `^process_.*$`                         | any           | True            | 2           | None        |

## Target index

| Target                              | Expected | What it isolates                                                            |
|-------------------------------------|----------|-----------------------------------------------------------------------------|
| `target_pass_basic`                 | PASS     | All four classes verbatim                                                   |
| `target_pass_regex_match`           | PASS     | `HandlerSet` adds a 4th `handle_*` method (still within `max_count=5`)      |
| `target_pass_classmethod_only`      | PASS     | `ClassmethodFactories.create` stays as `@classmethod`                        |
| `target_fail_below_min`             | FAIL     | `HandlerSet` has only `handle_create` (1 method, below `min_count=2`)        |
| `target_fail_above_max`             | FAIL     | `HandlerSet` has 6 `handle_*` methods (over `max_count=5`)                   |
| `target_fail_declared_only`         | FAIL     | `DeclaredHandlers` inherits `process_*` from a base instead of declaring it |
| `target_fail_wrong_method_kind`     | FAIL     | `ClassmethodFactories.create` is a regular instance method, not classmethod |

## How to re-run

```bash
python-arch-test --validate-declarations \
    --source example/rule_showcase/api005_method_set/reference

for t in target_pass_basic target_pass_regex_match target_pass_classmethod_only \
         target_fail_below_min target_fail_above_max target_fail_declared_only \
         target_fail_wrong_method_kind; do
  python-arch-test \
      --source example/rule_showcase/api005_method_set/reference \
      --target example/rule_showcase/api005_method_set/assignments/$t \
      --format json \
      --output example/rule_showcase/api005_method_set/reports/$t.report.json
done
```

See `findings.md` for the expected/observed verdict cross-check.
