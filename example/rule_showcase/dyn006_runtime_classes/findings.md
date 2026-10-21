# DYN006/DYN007 — findings

## Expected vs. observed

With `--dynamic`:

| Target                         | Expected | Observed                                                                                         | Status |
|--------------------------------|----------|--------------------------------------------------------------------------------------------------|--------|
| `target_pass_basic`            | PASS     | exit=0, 3 OK                                                                                     | OK     |
| `target_pass_runtime_wiring`   | PASS     | exit=0, 3 OK                                                                                     | OK     |
| `target_fail_missing_len`      | FAIL     | exit=1, 1 FAIL / 2 OK: `case 0: the class is abstract at run time; unimplemented: __len__`        | OK     |
| `target_fail_concrete_storage` | FAIL     | exit=1, 1 FAIL / 2 OK: `the class is concrete at run time: no abstract method is left unimplemented` | OK |
| `target_fail_export_arity`     | FAIL     | exit=1, 1 FAIL / 2 OK: `case 0: 'export' does not accept 1 positional argument(s)`               | OK     |

The reference run against itself passes. Without `--dynamic` every target
exits 0 with all rules `SKIPPED`.

## Capabilities exercised

- Abstract methods defined by a standard-library base (`MutableMapping`).
- Methods provided by a mixin and members bound in `__init__`.
- Protocol method arity checked with `inspect.signature(...).bind`.

## Limitations / gotchas

- Protocol annotations and return types are not compared; the static
  `implements_protocol` does that.
- `is_runtime_abstract_class` takes no cases: the class is only imported.

## Validation declaration check

`--validate-declarations` reports 0 diagnostics. The protocol argument of
`implements_runtime_protocol(Exporter, ...)` is a name, not a literal; it is
resolved from the reference, as for `implements_protocol`.
