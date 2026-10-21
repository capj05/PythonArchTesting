# DYN002 — `forbid_runtime_imports` showcase

The reference `report.py` is a report layer that must not reach storage
(`sqlite3`, `pickle`) or XML parsing; `xml.sax.saxutils` stays allowed for
escaping. Two markers cover the two moments a dependency shows:

- module-level `forbid_runtime_imports(...)` — imports the module and records
  what its code imports meanwhile;
- `forbid_runtime_calls("sqlite3", "pickle", ...)` on `render` — calls the
  function and records calls into those modules, so a module imported lazily
  inside it and then used is caught.

```bash
python-arch-test --source example/rule_showcase/dyn002_runtime_imports/reference \
    --targets-dir example/rule_showcase/dyn002_runtime_imports/assignments \
    --format json --dynamic
```

## Marker matrix exercised

| Reference entity | Marker                                                         | Observed                 |
|------------------|----------------------------------------------------------------|--------------------------|
| module `report`  | `forbid_runtime_imports("sqlite3", "pickle", "xml", allow=[...])` | imports at module import |
| `render`         | `forbid_runtime_calls("sqlite3", "pickle", cases=[...])`       | calls during the call    |

## Target index

| Target                       | Expected | What it isolates                                                                  |
|------------------------------|----------|-----------------------------------------------------------------------------------|
| `target_pass_basic`          | PASS     | Only `json` and the allowed `xml.sax.saxutils`                                    |
| `target_fail_dynamic_import` | FAIL     | `importlib.import_module("sql" + "ite3")` at import time — no static edge exists |
| `target_fail_lazy_import`    | FAIL     | `__import__("pickle")` inside `render` — module import is clean                   |
| `target_fail_xml_parser`     | FAIL     | `xml.dom.minidom`: under forbidden `xml`, outside the allow-list                  |

See `findings.md` for the expected vs observed verdicts.
