# API004 — `required_factory` showcase

The reference module declares the `required_factory` marker on six classes,
each exercising a distinct facet of the parameter set. Every target keeps
all six reference classes intact and modifies only the one relevant to the
scenario, so each verdict isolates a single concern.

## Parameter matrix exercised

| Reference class             | `satisfy_with`        | `name_match` | `aliases` | `detection_mode` | `return_annotation_mode` |
|-----------------------------|-----------------------|--------------|-----------|------------------|--------------------------|
| `ClassmethodFactory`        | `("classmethod",)`    | exact        | `("create",)` | strict (default)   | ignore (default)           |
| `StaticmethodFactory`       | `("staticmethod",)`   | exact        | `("build",)`  | strict             | ignore                     |
| `ConstructorOnly`           | `("constructor",)`    | any (default)| —             | strict             | ignore                     |
| `LenientMatch`              | default tuple         | exact        | `("make",)`   | lenient            | ignore                     |
| `StaticAttributeFactory`    | `("classmethod",)`    | exact        | `("make",)`   | strict             | ignore                     |
| `CheckedReturnAnnotation`   | default tuple         | any          | `("create",)` | strict             | check                      |

Defaults not shown: `allow_inherited=True`, `allow_missing=False`,
`signature_mode="compatible"`, `severity="error"`.

## Target index

| Target                                    | Expected | What it isolates                                                                  |
|-------------------------------------------|----------|-----------------------------------------------------------------------------------|
| `target_pass_classmethod_factory`         | PASS     | All six classes verbatim — verifies the classmethod-factory path                  |
| `target_pass_staticmethod_factory`        | PASS     | All verbatim — verifies the staticmethod-factory path                             |
| `target_pass_constructor_only`            | PASS     | `ConstructorOnly.__init__` satisfies the rule via `satisfy_with=("constructor",)` |
| `target_pass_lenient_match_by_name`       | PASS     | `LenientMatch.make` retains its signature under `detection_mode='lenient'`        |
| `target_pass_static_attribute_factory`    | PASS     | `make = classmethod(_make_impl)` assignment satisfies the classmethod requirement |
| `target_fail_missing_factory`             | FAIL     | `ClassmethodFactory.create` removed; no satisfying member remains                 |
| `target_fail_wrong_signature`             | FAIL     | `LenientMatch.make` retypes `raw: str -> raw: int`                                |
| `target_fail_return_annotation`           | FAIL     | `CheckedReturnAnnotation.create` returns `dict` under `return_annotation_mode="exact"` |

## How to re-run

```bash
python-arch-test --validate-declarations \
    --source example/rule_showcase/api004_factory/reference

for t in target_pass_classmethod_factory target_pass_staticmethod_factory \
         target_pass_constructor_only target_pass_lenient_match_by_name \
         target_pass_static_attribute_factory target_fail_missing_factory \
         target_fail_wrong_signature target_fail_return_annotation; do
  python-arch-test \
      --source example/rule_showcase/api004_factory/reference \
      --target example/rule_showcase/api004_factory/assignments/$t \
      --format json \
      --output example/rule_showcase/api004_factory/reports/$t.report.json
done
```

Reports land in `reports/` once the parent run dispatches the validation matrix.
