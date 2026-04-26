# Pattern Recipe Inventory

This note tracks the initial documentation-first pattern catalog. These are
compositions of existing public markers, not new engine features.

| Pattern | Core public markers | Depends on | Current limitations |
| --- | --- | --- | --- |
| Immutable value object | `required_attribute`, `required_constructor`, `does_not_have` | Attributes, constructors, negative member rules | Static checks cannot prove full runtime immutability; mutator detection is name-based unless you add stricter forbidden members. |
| Enum-backed domain type | `is_enum`, optionally `does_not_have`, `require_method_set` | Enum classification, optional negative member rules, optional method sets | `is_enum` checks enum-like classification, not business meaning or member values. |
| Repository / service contract | `required_method`, `required_factory`, `implements_protocol`, `does_not_have` | Required methods, factory rules, protocol conformance, negative member rules | Recipes can require a public contract shape, but they do not prove persistence semantics or transaction behavior. |
| Lifecycle / test-style class | `require_method_set`, `required_method`, `does_not_have` | Method-set cardinality, required methods, negative member rules | Method names and counts can be checked, but fixture ordering and runtime side effects are outside the static model. |
| Factory-backed type | `required_constructor`, `required_factory` | Constructors, factories | Candidate discovery and callable matching follow current constructor/factory rules only. |
| Layered domain object | `forbid_imports`, `does_not_have`, `subclass_of`, `not_subclass_of`, `implements_protocol` | Import rules, negative member rules, nominal rules, protocol rules | Layering recipes are static and local to the declared scope; they do not imply full package architecture enforcement by themselves. |

Constraints for the first pattern-catalog release:

- Use only markers documented in `docs/api-reference.md`.
- Prefer one-file, copyable snippets for the first four recipes.
- Add validation tests whenever a new snippet or recipe page is added.
