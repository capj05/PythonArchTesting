# API003 — findings

## Expected vs. observed

| Target                            | Expected | Observed              | Status |
|-----------------------------------|----------|-----------------------|--------|
| `target_pass_basic`               | PASS     | exit=0, 7 OK          | OK     |
| `target_pass_dataclass_field`     | PASS     | exit=0, 7 OK          | OK     |
| `target_pass_property_satisfies_attr` | PASS | exit=0, 7 OK          | OK     |
| `target_pass_inherited_ctor`      | PASS     | exit=0, 7 OK          | OK     |
| `target_fail_missing_attr`        | FAIL     | exit=1, 6 OK / 1 FAIL | OK     |
| `target_fail_class_storage`       | FAIL     | exit=1, 6 OK / 1 FAIL | OK     |
| `target_fail_wrong_attr_annotation` | FAIL   | exit=1, 6 OK / 1 FAIL | OK     |
| `target_fail_wrong_ctor_arity`    | FAIL     | exit=1, 6 OK / 1 FAIL | OK     |

## Defects observed

None — the previously catalogued DEFECT-1 has been fixed. See
"Fix history" below.

## Capabilities exercised

- instance vs class storage discrimination
- property satisfying an attribute requirement (passes when `@property` of
  the same name is present)
- dataclass field interpretation (passes via field annotation)
- `required_constructor` arity / parameter shape check
- `allow_inherited=True` accepts an inherited `__init__`
- attribute annotation enforcement (`annotation=str` correctly rejects a
  target attribute typed `int`)

## Fix history

- **DEFECT-1** (`required_attribute(annotation=str)` not enforced): fixed
  in `entities_extraction/annotations.py` by adding a special case in the
  marker-kwarg loop so that `required_attribute(annotation=...)` accepts
  both string-literal forms (`annotation="str"`) and bare type references
  (`annotation=str`, `annotation=list[int]`). Bare references were
  previously demoted to `unsupported` by `ast.literal_eval` and silently
  dropped from the compiled rule, leaving the evaluator with no
  constraint to check. The mechanism mirrors the existing
  `implements_protocol(protocol=...)` precedent in the same loop. The
  evaluator already calls `compare_annotation_text` correctly when an
  expected annotation is present; only the data flow needed restoring.
- Reference + pass-target HasName classes were updated from
  `self.name = name` to `self.name: str = name` so the instance attribute
  carries an explicit annotation that satisfies the now-enforced
  `annotation=str` constraint. Previously the bug masked the missing
  inline annotation.

## Validation declaration check

`--validate-declarations` reports 0 diagnostics.
