# Rule Showcase

Per-rule example projects that demonstrate every supported marker in
isolation, exercise its parameter surface, and validate observed
behaviour against expected outcomes via captured CLI reports.

The synthesis of capabilities, limitations, gotchas, and observed
defects across all 13 families lives in [`SUMMARY.md`](SUMMARY.md).

## Index

| Family                                                          | Markers covered                                                                                       |
|-----------------------------------------------------------------|--------------------------------------------------------------------------------------------------------|
| [`api001_signature/`](api001_signature/)                        | `required_entity_signature`                                                                            |
| [`api002_method/`](api002_method/)                              | `required_method`                                                                                      |
| [`api003_attribute_ctor/`](api003_attribute_ctor/)              | `required_attribute`, `required_constructor`                                                           |
| [`api004_factory/`](api004_factory/)                            | `required_factory`                                                                                     |
| [`api005_method_set/`](api005_method_set/)                      | `require_method_set`                                                                                   |
| [`api006_member_set/`](api006_member_set/)                      | `require_member_set`                                                                                   |
| [`dep001_imports/`](dep001_imports/)                            | `forbid_imports`                                                                                       |
| [`nom001_inheritance/`](nom001_inheritance/)                    | `subclass_of`, `not_subclass_of`, `inherits_directly_from`, `exact_type`                               |
| [`neg001_absence/`](neg001_absence/)                            | `does_not_have`                                                                                        |
| [`pro001_protocol/`](pro001_protocol/)                          | `implements_protocol`                                                                                  |
| [`mod001_modifiers/`](mod001_modifiers/)                        | `is_abstract_class`, `is_concrete_class`, `is_final_class`, `is_non_final_class`, `is_abstract_method`, `is_non_abstract_method`, `is_final_method`, `is_non_final_method` |
| [`enum001_enum/`](enum001_enum/)                                | `is_enum`                                                                                              |
| [`flw001_flow/`](flw001_flow/)                                  | `flow`, `enforce_flow`                                                                                 |

## Layout (per family)

```
<family>/
    README.md                      # parameter matrix and target index
    reference/
        config.conf                # single-target run config
        <module(s)>.py             # rule declarations using __archtest__
    assignments/
        target_pass_basic/         # passing baseline
        target_pass_<variant>/     # alternate passing scenarios (parameter flips)
        target_fail_<reason>/      # failing scenarios isolating one concern
    reports/                       # NOT checked in - generated on demand
        <target>.report.json       # JSON v2 output of the commands below
        <target>.report.md         # Markdown output of the commands below
    findings.md                    # expected vs. observed table + notes
```

The `reports/` directories are ignored by git (`.gitignore`:
`example/rule_showcase/*/reports/`), so a fresh checkout has none. Re-create the
ones you need with the commands below; `findings.md` records what those runs
produced.

## Re-running validation

For each family, before treating a green run as conclusive, validate the
reference declarations themselves:

```bash
python-arch-test --validate-declarations \
    --source example/rule_showcase/<family>/reference
```

To re-capture all reports for a family:

```bash
FAM=api005_method_set
for t in example/rule_showcase/$FAM/assignments/*/; do
    name=$(basename "$t")
    python-arch-test \
        --source example/rule_showcase/$FAM/reference \
        --target example/rule_showcase/$FAM/assignments/$name \
        --format json \
        --output example/rule_showcase/$FAM/reports/$name.report.json
    python-arch-test \
        --source example/rule_showcase/$FAM/reference \
        --target example/rule_showcase/$FAM/assignments/$name \
        --format markdown \
        --output example/rule_showcase/$FAM/reports/$name.report.md
done
```

Reading the captured JSON v2 reports — the `summary.results.status_counts`
block tells you OK / FAILED / SKIPPED / WARNING tallies; the `results[]`
array carries per-rule verdicts with `reason`, `errors`, and the matched
entity pair.

## Reading the findings

Each family's `findings.md` follows the same shape:

1. **Expected vs. observed** table — one row per target.
2. **Defects observed** — discrepancies between expected and observed
   verdicts, captured against the specific JSON report that reproduces
   them.
3. **Capabilities exercised** — a practical, user-facing inventory of
   the parameter surface that the showcase actually drives.
4. **Limitations / gotchas** — shapes the rule cannot express in v1, or
   surprising-but-by-design behaviour.
5. **Validation declaration check** — the `--validate-declarations`
   verdict for the reference.

The top-level [`SUMMARY.md`](SUMMARY.md) folds all of these together and
adds a "cross-cutting findings" section that groups patterns observed
across families (e.g. silent rule drop on misconfiguration, `name_match`
spelling drift, single-target Markdown output ergonomics).
