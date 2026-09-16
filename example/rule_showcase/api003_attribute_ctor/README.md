# API003 — `required_attribute` + `required_constructor`

Family #3 of the rule showcase. Demonstrates state-shape rules that attach to
**classes**: required attributes (instance vs class storage, dataclass fields,
properties, annotations) and required constructors (compatible vs exact
signature, inheritance handling).

## Why one marker per class

Both markers are class-level. Stacking multiple `__archtest__` annotations on
the same class collides on Python's `__annotations__` dict (the later
assignment overwrites the earlier). Coverage is therefore split across multiple
small classes, each carrying exactly one marker.

## Reference contract — class / parameter matrix

| Class | Marker | Parameters exercised |
|-------|--------|----------------------|
| `HasName` | `required_attribute` | `name`, `annotation=str`, `storage="instance"` |
| `HasVersion` | `required_attribute` | `name`, `annotation=str`, `storage="class"` |
| `HasPropertyOk` | `required_attribute` | `name`, `annotation=int`, `allow_property=True` |
| `HasDataclassField` | `required_attribute` | `name`, `annotation=int`, `interpret_dataclass_fields=True` |
| `HasCompatibleCtor` | `required_constructor` | `signature_mode="compatible"` |
| `HasExactCtor` | `required_constructor` | `signature_mode="exact"` |
| `CtorAllowInherited` | `required_constructor` | `allow_inherited=True` (no own `__init__`; inherits from `_CtorBase`) |

`_CtorBase` is a private helper providing the inheritable constructor for
`CtorAllowInherited`. It carries no marker.

## Targets

| Target | Expected | What the variation isolates |
|--------|----------|-----------------------------|
| `target_pass_basic` | PASS | All 7 classes verbatim |
| `target_pass_property_satisfies_attr` | PASS | `HasPropertyOk` keeps the `@property` (`allow_property=True`) |
| `target_pass_dataclass_field` | PASS | `HasDataclassField` keeps `count: int = 0` (dataclass field interpreted) |
| `target_pass_inherited_ctor` | PASS | `CtorAllowInherited` inherits `__init__(self, value: int)` from `_CtorBase` |
| `target_fail_missing_attr` | FAIL | `HasName.__init__` accepts `name` but never assigns `self.name` |
| `target_fail_wrong_attr_annotation` | FAIL | `HasVersion` declares `VERSION: int = 1` instead of `str` |
| `target_fail_class_storage` | FAIL | `HasName` puts `name: str = "x"` at class level (violates `storage="instance"`) |
| `target_fail_wrong_ctor_arity` | FAIL | `HasExactCtor.__init__` adds an `extra: int = 0` param (violates `signature_mode="exact"`) |

Every target re-exports all 7 classes; only the relevant class differs from the
reference. Targets carry no `__archtest__` annotations.

## How to re-run

```bash
python -m pythonarchtesting.cli \
    --source example/rule_showcase/api003_attribute_ctor/reference \
    --target example/rule_showcase/api003_attribute_ctor/assignments/target_pass_basic \
    --format markdown --output example/rule_showcase/api003_attribute_ctor/reports/

# Multi-target:
python -m pythonarchtesting.cli \
    --source example/rule_showcase/api003_attribute_ctor/reference \
    --targets-dir example/rule_showcase/api003_attribute_ctor/assignments \
    --format markdown --output example/rule_showcase/api003_attribute_ctor/reports/
```

Targets covered:

- `target_pass_basic`
- `target_pass_property_satisfies_attr`
- `target_pass_dataclass_field`
- `target_pass_inherited_ctor`
- `target_fail_missing_attr`
- `target_fail_wrong_attr_annotation`
- `target_fail_class_storage`
- `target_fail_wrong_ctor_arity`
