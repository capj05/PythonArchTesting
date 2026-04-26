# Pattern Recipes

Pattern recipes are higher-level documentation bundles built from the existing
marker API. They are not new engine rule families, and they do not add new
compiler or evaluator semantics.

Use this page when you already know the primitive markers exist, but want a
copyable starting point for a common architecture constraint.

## How To Read These Recipes

Each recipe follows the same structure:

1. Pattern name
2. Intent
3. When to use
4. Primitive rule mapping
5. Minimal reference snippet
6. What this does not guarantee
7. Variations
8. Expected report behavior
9. Copy-ready snippet

The snippets are intentionally transparent. You should be able to paste one
into a reference project and still see exactly which primitive markers are
enforcing the pattern.

## Recipe Limits

These recipes are compositions of current public markers. They do not create a
meta-DSL, and they do not guarantee behavior outside the static checks already
documented in the API reference.

In practice, that means:

- a recipe can require names, signatures, constructors, factories, attributes,
  import boundaries, and nominal or structural relationships
- a recipe cannot prove runtime semantics such as side effects, persistence
  correctness, or deep immutability

## Recipe Index

- [Immutable Value Object](#immutable-value-object)
- [Enum-Backed Domain Type](#enum-backed-domain-type)
- [Repository Or Service Contract](#repository-or-service-contract)
- [Lifecycle Or Test-Style Class](#lifecycle-or-test-style-class)

## Immutable Value Object

### Intent

Express a small value-carrying type that must expose a stable set of fields and
must not expose obvious setter-style mutation methods.

### When To Use

Use this when the architectural contract is "this class behaves like a value
object" and you want a copyable static baseline rather than a custom rule.

### Primitive Rule Mapping

- `required_attribute(...)`
- `required_constructor(...)`
- `does_not_have(...)`

### Minimal Reference Snippet

```python
from typing import Annotated
from pythonarchtesting.rules import (
    does_not_have,
    required_attribute,
    required_constructor,
)


class Money:
    __archtest__: Annotated[
        None,
        required_constructor(signature_mode="any"),
        required_attribute("amount", storage="instance"),
        required_attribute("currency", storage="instance"),
        does_not_have("set_amount", member_kind="method"),
        does_not_have("update_currency", member_kind="method"),
    ]

    def __init__(self, amount: int, currency: str) -> None:
        self.amount = amount
        self.currency = currency
```

### What This Does Not Guarantee

This recipe does not prove true runtime immutability. It only checks for the
required constructor and fields plus the absence of the forbidden mutator
methods you declare.

### Variations

- Use `allow_property=True` on `required_attribute(...)` when the target may
  expose read-only properties instead of raw instance attributes.
- Use `declared_only=True` on attributes when inherited state should not count.
- Expand the forbidden method list with project-local mutator names such as
  `replace`, `merge`, or `apply`.

### Expected Report Behavior

Missing fields or constructor candidates fail normally. Forbidden mutator names
fail under `NEG001`. If a target keeps the right state shape and avoids the
forbidden methods, the recipe passes without any new pattern-specific rule.

### Copy-Ready Snippet

Full snippet: `docs/snippets/patterns/immutable_value_object.py`

## Enum-Backed Domain Type

### Intent

Require that a matched target class is actually implemented as an enum-like
type, with optional helper constraints layered on top.

### When To Use

Use this when the domain concept should be represented as a closed set of
values rather than a mutable service or data holder.

### Primitive Rule Mapping

- `is_enum(...)`
- `does_not_have(...)`
- optional `require_method_set(...)`

### Minimal Reference Snippet

```python
from enum import Enum
from typing import Annotated
from pythonarchtesting.rules import does_not_have, is_enum


class OrderStatus(Enum):
    __archtest__: Annotated[
        None,
        is_enum(),
        does_not_have("mutate", member_kind="method"),
    ]

    NEW = "new"
    PAID = "paid"
    CANCELLED = "cancelled"
```

### What This Does Not Guarantee

This recipe does not validate the business meaning of enum members, their
values, or their ordering. It only checks enum classification and any extra
primitive constraints you add.

### Variations

- Add `require_method_set(...)` when every enum type in a family must provide a
  helper such as `from_code`.
- Add more `does_not_have(...)` declarations when helper names should stay
  minimal or non-mutating.

### Expected Report Behavior

Targets that are not classified as enum-like fail the enum rule directly.
Targets that are enums but expose forbidden helper methods fail through the
negative member rule.

### Copy-Ready Snippet

Full snippet: `docs/snippets/patterns/enum_domain_type.py`

## Repository Or Service Contract

### Intent

Package a common service-contract shape around required read methods, optional
factory entrypoints, and a few explicit forbidden members.

### When To Use

Use this when you need a transparent recipe for "objects in this role must
expose a stable service surface" without creating a dedicated repository rule.

### Primitive Rule Mapping

- `required_method(...)`
- `required_factory(...)`
- `does_not_have(...)`
- optional `implements_protocol(...)`

### Minimal Reference Snippet

```python
from typing import Annotated
from pythonarchtesting.rules import (
    does_not_have,
    required_factory,
    required_method,
)


class RepositoryReference:
    __archtest__: Annotated[
        None,
        does_not_have("commit", member_kind="method"),
    ]

    @classmethod
    def from_config(cls, url: str):
        __archtest__: Annotated[
            None,
            required_factory(
                signature_mode="any",
                name_match="alias",
                aliases=["build", "open"],
            ),
        ]
        return cls()

    def get(self, item_id: str) -> object:
        __archtest__: Annotated[
            None,
            required_method(
                name_match="alias",
                aliases=["load", "fetch"],
            ),
        ]
        return object()
```

### What This Does Not Guarantee

This recipe does not prove repository semantics, transaction handling, or data
source correctness. It only checks the shape of the public contract you model
with the primitive markers.

### Variations

- Add `implements_protocol(...)` when structural typing should remain the
  source of truth for the same contract.
- Set `allow_missing=True` on optional methods such as `save`.
- Narrow `required_factory(...)` with `satisfy_with=("classmethod",)` when only
  named constructors should satisfy the recipe.

### Expected Report Behavior

Missing read methods fail under `API002`, missing accepted factories fail under
`API004`, and persistence-leak helper names fail under `NEG001`.

### Copy-Ready Snippet

Full snippet: `docs/snippets/patterns/repository_contract.py`

## Lifecycle Or Test-Style Class

### Intent

Describe a class that must expose setup or teardown hooks plus at least one
test-style method, without baking test-runner semantics into the engine.

### When To Use

Use this when you want a compact static contract for internal test helpers,
plugin lifecycles, or framework-like classes that rely on well-known hook
names.

### Primitive Rule Mapping

- `require_method_set(...)`
- `required_method(...)`
- `does_not_have(...)`

### Minimal Reference Snippet

```python
from typing import Annotated
from pythonarchtesting.rules import (
    does_not_have,
    require_method_set,
    required_method,
)


class TestCaseStyle:
    __archtest__: Annotated[
        None,
        require_method_set(name_match="regex", pattern=r"test_.*", min_count=1),
        does_not_have("debug", member_kind="method"),
    ]

    def setUp(self) -> None:
        __archtest__: Annotated[
            None,
            required_method(signature_mode="any", allow_missing=True),
        ]

    def tearDown(self) -> None:
        __archtest__: Annotated[
            None,
            required_method(signature_mode="any", allow_missing=True),
        ]
```

### What This Does Not Guarantee

This recipe does not prove test execution order, fixture idempotence, or that a
hook is actually called by a runner. It only captures the expected names and
method presence constraints.

### Variations

- Use `method_kind="class"` in `require_method_set(...)` for class-level hook
  registries.
- Replace `debug` with project-local helper names or a regex-driven negative
  recipe elsewhere in the catalog.
- Tighten `required_method(...)` to `signature_mode="exact"` when hook
  signatures are part of the contract.

### Expected Report Behavior

Targets without any `test_.*` methods fail the method-set rule. Missing
optional hooks produce `SKIPPED` instead of `FAILED`, and forbidden helpers
still fail normally through the negative member rule.

### Copy-Ready Snippet

Full snippet: `docs/snippets/patterns/lifecycle_hooks.py`

## Maintainer Note

New recipes should:

- use only public markers documented in `docs/api-reference.md`
- include a limitations section
- include at least one snippet file
- add or update validation tests when new recipe files are introduced
