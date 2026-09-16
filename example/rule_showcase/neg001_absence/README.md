# NEG001 — `does_not_have` showcase

Reference module declares one `does_not_have` marker per class so each target
isolates a single concern (explicit-name absence, alias set, regex pattern,
member-kind filtering, declared-only enforcement).

## Marker matrix exercised

| Reference class       | `name_match` | `name` / `aliases` / `pattern`                              | `member_kind` | `declared_only` |
|-----------------------|--------------|-------------------------------------------------------------|---------------|-----------------|
| `NoSecret`            | exact        | `"secret"`                                                  | any           | False           |
| `NoDangerousAliases`  | alias        | `("eval_input", "exec_code", "shell_out")`                  | any           | False           |
| `NoDebugMethods`      | regex        | `r"^debug_.*$"`                                             | method        | False           |
| `NoConstantsClass`    | regex        | `r"^[A-Z_]+$"`                                              | constant      | False           |
| `DeclaredNoSecret`    | exact        | `"secret"`                                                  | any           | True            |

## Target index

| Target                              | Expected | What it isolates                                                         |
|-------------------------------------|----------|--------------------------------------------------------------------------|
| `target_pass_basic`                 | PASS     | Five compliant classes, no forbidden members                             |
| `target_pass_inherited_allowed`     | PASS     | `DeclaredNoSecret(_Base)` inherits `secret` — allowed by `declared_only` |
| `target_fail_explicit_name`         | FAIL     | `NoSecret` defines a `secret` attribute                                  |
| `target_fail_alias`                 | FAIL     | `NoDangerousAliases` defines `exec_code`                                 |
| `target_fail_regex_match`           | FAIL     | `NoDebugMethods` defines `debug_dump(self)`                              |
| `target_fail_member_kind`           | FAIL     | `NoConstantsClass` defines `MAX_RETRIES = 3` (constant)                  |

## How to re-run

```bash
python-arch-test --validate-declarations \
    --source example/rule_showcase/neg001_absence/reference

for t in target_pass_basic target_pass_inherited_allowed \
         target_fail_explicit_name target_fail_alias \
         target_fail_regex_match target_fail_member_kind; do
  python-arch-test \
      --source example/rule_showcase/neg001_absence/reference \
      --target example/rule_showcase/neg001_absence/assignments/$t \
      --format json \
      --output example/rule_showcase/neg001_absence/reports/$t.report.json
done
```

See `findings.md` for the expected/observed verdict cross-check.
