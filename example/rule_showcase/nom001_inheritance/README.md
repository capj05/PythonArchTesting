# NOM001 — nominal inheritance markers showcase

Reference module declares one nominal-inheritance marker per class so each
target isolates a single concern (subclass relationship, exact nominal type,
forbidden ancestry, or direct-inheritance requirement).

## Marker matrix exercised

| Reference class | Marker                          | `base`   | Semantics                                     |
|-----------------|---------------------------------|----------|-----------------------------------------------|
| `Dog`           | `subclass_of`                   | `Animal` | Must be a subclass of Animal (transitive OK)  |
| `Sparrow`       | `exact_type`                    | `Bird`   | Type must be exactly Bird                     |
| `Car`           | `not_subclass_of`               | `Animal` | Must NOT be a subclass of Animal              |
| `Robin`         | `inherits_directly_from`        | `Bird`   | Must inherit DIRECTLY from Bird (not via)     |

All markers use default `severity="error"` and no custom `message`.

## Target index

| Target                                  | Expected | What it isolates                                                                  |
|-----------------------------------------|----------|-----------------------------------------------------------------------------------|
| `target_pass_basic`                     | PASS     | All four classes verbatim                                                         |
| `target_pass_transitive_subclass`       | PASS     | `Dog` reaches Animal via `Canine -> Mammal -> Animal` (transitive accepted)       |
| `target_fail_subclass_required`         | FAIL     | `Dog(Vehicle)` — no longer a subclass of Animal                                   |
| `target_fail_exact_type_violated`       | FAIL     | `Sparrow(Mammal)` — exact nominal type is no longer Bird                          |
| `target_fail_not_subclass_violated`     | FAIL     | `Car(Animal)` — Car becomes a subclass of Animal, which is forbidden              |
| `target_fail_direct_inherit_violated`   | FAIL     | `Robin(Sparrow)` — Robin reaches Bird only transitively, not directly             |

## How to re-run

```bash
python-arch-test --validate-declarations \
    --source example/rule_showcase/nom001_inheritance/reference

for t in target_pass_basic target_pass_transitive_subclass \
         target_fail_subclass_required target_fail_exact_type_violated \
         target_fail_not_subclass_violated target_fail_direct_inherit_violated; do
  python-arch-test \
      --source example/rule_showcase/nom001_inheritance/reference \
      --target example/rule_showcase/nom001_inheritance/assignments/$t \
      --format json \
      --output example/rule_showcase/nom001_inheritance/reports/$t.report.json
done
```

See `findings.md` (added by the parent run) for the expected/observed verdict cross-check.
