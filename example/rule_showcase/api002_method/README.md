# API002 -- `required_method` showcase

Reference module declares a single `Service` class whose methods each
carry an `__archtest__` annotation pinning a different combination of
`required_method` parameters. Each target then exercises one specific
concern at a time so a single verdict isolates a single behaviour.

## Parameter matrix exercised

| Reference method   | `signature_mode` | `enforce_method_kind` | `allow_missing` | `declared_only` | `name_match` / `aliases`                      |
|--------------------|------------------|-----------------------|-----------------|-----------------|-----------------------------------------------|
| `process`          | compatible (default) | True (default)    | False (default) | False (default) | exact (default)                               |
| `validate`         | compatible (default) | True (default)    | False (default) | False (default) | alias / `["validate", "check", "verify"]`     |
| `compute`          | compatible           | True (default)    | False (default) | False (default) | exact (default)                               |
| `count_items`      | compatible (default) | True              | False (default) | False (default) | exact (default)                               |
| `helper`           | compatible (default) | True (default)    | False (default) | False           | exact (default)                               |
| `internal_check`   | compatible (default) | True (default)    | False (default) | True            | exact (default)                               |
| `optional_hook`    | compatible (default) | True (default)    | True            | False (default) | exact (default)                               |

## Target index

| Target                                | Expected verdict | What it isolates                                                              |
|---------------------------------------|------------------|-------------------------------------------------------------------------------|
| `target_pass_basic`                   | PASS             | All methods declared on the class with matching signatures and method kinds  |
| `target_pass_alias_match`             | PASS             | `validate` renamed to `check`, allowed by `aliases=[..., "check", ...]`      |
| `target_fail_missing_method`          | FAIL             | `process` omitted entirely; default `allow_missing=False` rejects this        |
| `target_fail_wrong_signature`         | FAIL             | `compute` drops parameter `y` and changes return type                         |
| `target_fail_method_kind_mismatch`    | FAIL             | `count_items` is `@classmethod`, but rule has `enforce_method_kind=True`     |
| `target_pass_inherited`               | PASS             | `helper` inherited from base class; rule allows it (`declared_only=False`)   |
| `target_fail_declared_only`           | FAIL             | `internal_check` inherited; rule has `declared_only=True`                    |

## How to re-run

```bash
python-arch-test --validate-declarations \
    --source example/rule_showcase/api002_method/reference

for t in target_pass_basic target_pass_alias_match \
         target_fail_missing_method target_fail_wrong_signature \
         target_fail_method_kind_mismatch target_pass_inherited \
         target_fail_declared_only; do
  python-arch-test \
      --source example/rule_showcase/api002_method/reference \
      --target example/rule_showcase/api002_method/assignments/$t \
      --format json \
      --output example/rule_showcase/api002_method/reports/$t.report.json
done
```

See `findings.md` (added by the parent run) for the expected vs observed
verdict cross-check.
