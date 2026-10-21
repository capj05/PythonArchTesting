# DYN002 — findings

## Expected vs. observed

With `--dynamic`:

| Target                       | Expected | Observed                                                                                                   | Status |
|------------------------------|----------|------------------------------------------------------------------------------------------------------------|--------|
| `target_pass_basic`          | PASS     | exit=0, 2 OK                                                                                               | OK     |
| `target_fail_dynamic_import` | FAIL     | exit=1, 1 FAIL / 1 OK: `imported sqlite3 at report.py:14`; `render` never calls the driver                 | OK     |
| `target_fail_lazy_import`    | FAIL     | exit=1, 1 OK / 1 FAIL: `case 0: render calls pickle:dumps (line 15)`                                       | OK     |
| `target_fail_xml_parser`     | FAIL     | exit=1, 1 OK / 1 FAIL: `imported xml.dom.minidom at report.py:10`                                          | OK     |

Without `--dynamic` every target exits 0 with both rules `SKIPPED`.

## Capabilities exercised

- Imports by computed name through `importlib.import_module`.
- `__import__` inside a function, seen only when the function runs.
- Forbidden prefix with an allow-list exemption (`xml` vs `xml.sax.saxutils`).
- File and line of each offending import in the result.

## Limitations / gotchas

- `forbid_runtime_imports` sees only code that importing the module executes;
  `target_fail_lazy_import` passes it, and only `forbid_runtime_calls` on
  `render` catches the lazily imported module, once it is used. A lazy import
  that is never used is not seen.
- `pickle.dumps` is implemented in `_pickle`; the call is reported under the
  public name `pickle`.
- `from xml.dom import minidom` is reported as `xml.dom.minidom`, the same as
  `import xml.dom.minidom`; the parent packages are not reported separately.
- Imports the standard library makes internally (`json` importing `re`, for
  example) are not attributed to the target.

## Validation declaration check

`--validate-declarations` reports 0 diagnostics.
