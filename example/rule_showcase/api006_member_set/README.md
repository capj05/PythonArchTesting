# API006 — `require_member_set` showcase

Reference module declares one `require_member_set` marker per class so that
each target isolates a single concern (member-kind filtering, dataclass-field
interpretation, property counting bounds, the `allow_property` toggle).

## Marker matrix exercised

| Reference class    | `member_kinds`    | Extra options                                        | `min_count` | `max_count` |
|--------------------|-------------------|------------------------------------------------------|-------------|-------------|
| `MixedMembers`     | `("any",)`        | —                                                    | 3           | 10          |
| `DataclassPayload` | `("attribute",)`  | `interpret_dataclass_fields=True`                    | 2           | 5           |
| `PropertyHolder`   | `("property",)`   | —                                                    | 2           | 2           |
| `MethodOnly`       | `("method",)`     | `allow_property=False`                               | 2           | None        |

## Target index

| Target                                | Expected | What it isolates                                                           |
|---------------------------------------|----------|----------------------------------------------------------------------------|
| `target_pass_basic`                   | PASS     | All four classes verbatim                                                  |
| `target_pass_dataclass_fields`        | PASS     | `DataclassPayload` keeps 3 dataclass fields (within 2..5)                  |
| `target_pass_property_count`          | PASS     | `PropertyHolder` keeps exactly 2 properties                                |
| `target_fail_below_min`               | FAIL     | `MixedMembers` reduced to only 2 members (below `min_count=3`)             |
| `target_fail_above_max`               | FAIL     | `PropertyHolder` adds a 3rd property (over `max_count=2`)                  |
| `target_fail_member_kind_mismatch`    | FAIL     | `MethodOnly` replaces methods with constants — 0 methods                   |
| `target_fail_no_property_allowed`     | FAIL     | `MethodOnly` adds a `@property` which `allow_property=False` forbids       |

## How to re-run

```bash
python-arch-test --validate-declarations \
    --source example/rule_showcase/api006_member_set/reference

for t in target_pass_basic target_pass_dataclass_fields target_pass_property_count \
         target_fail_below_min target_fail_above_max \
         target_fail_member_kind_mismatch target_fail_no_property_allowed; do
  python-arch-test \
      --source example/rule_showcase/api006_member_set/reference \
      --target example/rule_showcase/api006_member_set/assignments/$t \
      --format json \
      --output example/rule_showcase/api006_member_set/reports/$t.report.json
done
```

See `findings.md` for the expected/observed verdict cross-check.
