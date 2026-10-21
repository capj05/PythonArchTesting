# DYN006/DYN007 — runtime class showcase

Three class contracts that only Python can settle at run time:

- `Inventory` derives from `collections.abc.MutableMapping`; which abstract
  methods it must implement is defined by the standard library —
  `is_runtime_concrete_class`;
- `Storage` must stay an abstract base — `is_runtime_abstract_class`;
- `CsvExporter` instances must satisfy the `Exporter` protocol (`name` and
  `export(rows)`), wherever the members come from —
  `implements_runtime_protocol`.

```bash
python-arch-test --source example/rule_showcase/dyn006_runtime_classes/reference \
    --targets-dir example/rule_showcase/dyn006_runtime_classes/assignments \
    --format json --dynamic
```

## Marker matrix exercised

| Reference entity          | Marker                                              |
|---------------------------|-----------------------------------------------------|
| `inventory:Inventory`     | `is_runtime_concrete_class(cases=[{"args": []}])`   |
| `inventory:Storage`       | `is_runtime_abstract_class()`                       |
| `inventory:CsvExporter`   | `implements_runtime_protocol(Exporter, cases=[...])` |

## Target index

| Target                         | Expected | What it isolates                                                                  |
|--------------------------------|----------|-----------------------------------------------------------------------------------|
| `target_pass_basic`            | PASS     | Same classes as the reference                                                     |
| `target_pass_runtime_wiring`   | PASS     | `__len__` from a mixin; `name` and `export` set in `__init__`                     |
| `target_fail_missing_len`      | FAIL     | `Inventory` lacks `__len__`, required by the standard library's `Sized`          |
| `target_fail_concrete_storage` | FAIL     | `Storage.save` implemented: the base is no longer abstract                        |
| `target_fail_export_arity`     | FAIL     | `export()` takes no rows: present, but not callable as the protocol says          |

Targets do not carry `__archtest__` metadata; the markers live only on the
reference side.

See `findings.md` for the expected vs observed verdicts.
