# API001 — `required_entity_signature` showcase

Reference module declares the same rule with **different parameter
combinations** on each function so that one target can demonstrate the
verdict for one specific concern at a time.

## Parameter matrix exercised

| Reference function | `mode`        | `allow_extra_params` | `allow_param_rename` | `return_annotation` |
|--------------------|---------------|----------------------|----------------------|---------------------|
| `compatible_baseline` | compatible (default) | True (default)   | False (default)      | warning (default)   |
| `flexible_extras`     | compatible            | True              | False                | warning             |
| `exact_strict`        | exact                 | False             | False                | warning             |
| `rename_allowed`      | compatible            | True              | True                 | warning             |
| `rename_forbidden`    | compatible            | True              | False                | warning             |
| `must_keep_return`    | compatible            | True              | False                | error               |
| `return_ignore`       | compatible            | True              | False                | ignore              |

## Target index

| Target                              | Expected verdict | What it isolates                                                      |
|-------------------------------------|------------------|-----------------------------------------------------------------------|
| `target_pass_basic`                 | PASS             | All signatures verbatim                                                |
| `target_pass_extras_compatible`     | PASS             | `flexible_extras` adds two defaulted kw-only params                    |
| `target_pass_renamed`               | PASS             | `rename_allowed` renames `value -> magnitude`                          |
| `target_pass_return_ignore_drift`   | PASS             | `return_ignore` returns `list[str]` instead of `dict[str, str]`        |
| `target_fail_missing_param`         | FAIL             | `compatible_baseline` drops parameter `b`                              |
| `target_fail_renamed_forbidden`     | FAIL             | `rename_forbidden` renames `value -> magnitude`                        |
| `target_fail_exact_extras`          | FAIL             | `exact_strict` adds an extra kw-only param                             |
| `target_fail_wrong_return`          | FAIL             | `must_keep_return` returns `list[str]` instead of `dict[str, str]`     |

## How to re-run

```bash
python-arch-test --validate-declarations \
    --source example/rule_showcase/api001_signature/reference

for t in target_pass_basic target_pass_extras_compatible target_pass_renamed \
         target_pass_return_ignore_drift target_fail_missing_param \
         target_fail_renamed_forbidden target_fail_exact_extras \
         target_fail_wrong_return; do
  python-arch-test \
      --source example/rule_showcase/api001_signature/reference \
      --target example/rule_showcase/api001_signature/assignments/$t \
      --format json \
      --output example/rule_showcase/api001_signature/reports/$t.report.json
done
```

See `findings.md` for the expected/observed verdict cross-check.
