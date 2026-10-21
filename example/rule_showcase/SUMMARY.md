# Rule Showcase — Synthesis Report

This document synthesises the per-family `findings.md` reports across all
22 showcases. For each family it captures (a) the practical
parameter surface, (b) limitations / things the rule cannot express, (c)
behavioural gotchas observed during validation, and (d) defects — cases
where the observed verdict diverged from the expected verdict.

A "defect" here is an asymmetry between the rule's documented intent and
its observed runtime behaviour, captured against a specific reference +
target pair so it can be reproduced. A "limitation" is a known shape
that the rule cannot express in v1; it is not a bug.

---

## API001 — `required_entity_signature`

**Capabilities**
- `mode="compatible"` (default) and `mode="exact"` for parameter-shape
  checks.
- `allow_param_rename=True/False` controls whether positional renames
  are tolerated.
- `allow_extra_params=True/False` allows additional optional params.
- `return_annotation` knob: `"warning"` (default), `"error"`, `"ignore"`.

**Defects observed**
- None — the previously catalogued DEFECT-1 (`allow_extra_params=True`
  not propagating through the matcher) and DEFECT-2
  (`return_annotation="ignore"` not suppressing the return-only sibling
  rule) have both been fixed. See `api001_signature/findings.md` §
  Fix history for the resolutions.

---

## API002 — `required_method`

**Capabilities**
- Existence check + signature compatibility (re-uses API001 evaluator).
- `declared_only=True` skips inherited methods.
- Aliases support classmethod / staticmethod parity when the canonical
  name differs.

**Notes**
- Inherits API001's defects in their narrow form: param-shape vs
  return-only split. For method-level callers, the same caveats apply.

---

## API003 — `required_attribute` / `required_constructor`

**Capabilities**
- Attribute presence (instance / class storage / property).
- Dataclass-field interpretation as attribute satisfaction.
- Constructor existence + signature; `allow_inherited=True` accepts an
  inherited `__init__`.

**Defects observed**
- None — the previously catalogued DEFECT-1
  (`required_attribute(annotation=str)` not enforced) has been fixed.
  See `api003_attribute_ctor/findings.md` § Fix history.

---

## API004 — `required_factory`

**Capabilities**
- `@classmethod` and `@staticmethod` factory shapes.
- `satisfy_with=("constructor",)` — admits plain `__init__` as a
  factory; default also includes `constructor`.
- `detection_mode` ∈ {`"extended"`, `"strict"`}.
- `return_annotation_mode` ∈ {`"compatible"`, `"exact"`, `"ignore"`}.
- `aliases=` for canonical factory names.

**Defects observed** — None — fixed.
  See `api004_factory/findings.md` § Fix history. The static-attribute
  factory pattern `make = classmethod(_make_impl)` now compiles
  correctly, the default `satisfy_with` no longer admits `__init__`
  when the caller specifies a name constraint, and invalid
  `detection_mode` / `return_annotation_mode` values now produce a
  visible FAILED rule result instead of being silently dropped.

---

## API005 — `require_method_set`

**Capabilities**
- `name_match` ∈ {`"any"`, `"regex"`, `"names"`}.
- `min_count` / `max_count` cardinality bounds.
- `declared_only=True` skips inherited methods.
- `method_kind` ∈ {`"any"`, `"instance"`, `"classmethod"`, `"staticmethod"`}.

**Defects observed** — None — fixed.
  See `api005_method_set/findings.md` § Fix history. Misconfigured
  rules (invalid `method_kind`, `names` as tuple, invalid `name_match`,
  out-of-range counts, etc.) now produce a visible FAILED rule result
  via the sentinel-rule pattern instead of being silently dropped after
  `compiler_invalid_declaration` evidence.

**Parameter discoveries**
- `name_match="alias"` is **not** accepted here — that spelling belongs
  to `does_not_have`. Use `name_match="names"`.
- `method_kind="class"` / `"static"` are NOT accepted; full names are
  required.
- `names` must be a Python `list`, not a tuple.
- Misconfigured rules now FAIL visibly instead of being silently
  dropped — sentinel `rule_id` starts with
  `API005/require_method_set/invalid_declaration/`.

---

## API006 — `require_member_set`

**Capabilities**
- `member_kinds` filter — `attribute`, `dataclass_field`, `property`,
  `cached_property`, descriptors.
- `min_count` / `max_count` cardinality.
- `name_match` consistent with API005.
- A single class can satisfy two `require_member_set` rules targeting
  different member kinds simultaneously.

**Defects observed** — None — fixed.
  See `api006_member_set/findings.md` § Fix history. Misconfigured
  rules (invalid `member_kinds`, `name_match`, `storage`,
  `descriptor_kinds`, `constructor_kind`, `method_kind`, out-of-range
  counts, `names` as tuple, etc.) now produce a visible FAILED rule
  result via the sentinel-rule pattern instead of being silently
  dropped after `compiler_invalid_declaration` evidence. Sentinel
  `rule_id` starts with
  `API006/require_member_set/invalid_declaration/`.

---

## DEP001 — `forbid_imports`

**Capabilities**
- `mode="direct"` (AST-only) and `mode="reachable"` (default; transitive
  graph reachability).
- `scope="module"` and `scope="package"` — package scope catches imports
  anywhere in the package.
- `allow=` exception list.
- `if TYPE_CHECKING:` imports ignored by both modes.

**Defects observed**
- **DEFECT-1** — `ignore_globs` does NOT prevent intermediate hops in
  reachable mode. The filter applies to the *importer* file path, not
  to intermediate hops in the reachability graph. A "trusted shim" is
  not expressible via `ignore_globs`; callers must drop reachable mode
  or extend `allow=` with the intermediate's transitive set. See
  `dep001_imports/findings.md` § DEFECT-1.

---

## NOM001 — `subclass_of` / `exact_type` / `not_subclass_of` / `inherits_directly_from`

**Capabilities**
- `subclass_of("Base")` — direct + transitive subclasses.
- `not_subclass_of("Base")` — passes for unrelated types.
- `inherits_directly_from("Parent")` — fails if an intermediate parent
  is inserted.
- `exact_type("X")` — passes only when the target class **is** the
  source class named X (entity identity, not name).

**Gotchas**
- `exact_type` resolves "X" to the matched target counterpart of source
  class X, then compares against the matched target counterpart of the
  declaring class. The practical use is therefore
  `exact_type("Self")` on `class Self` to forbid subclass substitution
  in the target. Attaching `exact_type` to a class that *inherits* from
  the named base — a common first-time misuse — is always FAILED.
- Base names must be strings, not type objects: passing a Python `type`
  emits `compiler_invalid_base_reference` and the rule is dropped.

---

## NEG001 — `does_not_have`

**Capabilities**
- Explicit name match (`names=[...]`).
- Regex match (`name_match="regex"`).
- Alias match (`name_match="alias"` with `aliases=[...]`).
- Member-kind filter scopes the absence check to a specific kind.

**Gotchas**
- `name_match="alias"` (singular) is correct here; the positive-set
  rules use `name_match="names"` (plural). Mixing them up emits
  `compiler_invalid_declaration` and silently drops the rule.

---

## PRO001 — `implements_protocol`

**Capabilities**
- Structural conformance (no inheritance required).
- Method-level signature compatibility (default; extra optional params
  accepted in target).
- Return-annotation enforcement.
- Method-kind enforcement (a `@classmethod` in the protocol cannot be
  satisfied by an instance method).
- `signature_mode="exact"` — exact parameter list match.

**Notes**
- Resolves the protocol type via the same source-target entity table
  as `subclass_of`. Protocols declared outside the source tree cannot
  be referenced.

---

## MOD001 — modifier markers

`is_abstract_class`, `is_concrete_class`, `is_final_class`,
`is_non_final_class`, `is_abstract_method`, `is_non_abstract_method`,
`is_final_method`, `is_non_final_method`.

**Capabilities**
- Class-level: detects `@abstractmethod` membership for abstract /
  concrete; `typing.final` decoration for final / non-final.
- Method-level: detects `@abstractmethod` decorator and `typing.final`
  on the method.
- Each rule keys off only its specific predicate — a single mismatch
  produces exactly one FAIL while the other 7 modifier rules stay
  green.

**Notes**
- "Abstract" is recognized via `@abstractmethod` only; raising
  `NotImplementedError` is not treated as abstract.
- "Final" is recognized via `@typing.final` (or
  `typing_extensions.final`); Python provides no other signal.

---

## ENUM001 — `is_enum`

**Capabilities**
- Detects subclasses of `enum.Enum`, `enum.IntEnum`, `enum.StrEnum`,
  `enum.Flag`, plus transitive enum bases declared in the project.
- Negative case: regular class fails.

**Notes**
- The rule does not differentiate between Enum flavours. To enforce a
  flavour combine with `subclass_of("IntEnum")`.

---

## FLW001 — `flow` / `enforce_flow`

**Capabilities**
- Linear stage ordering through `flow(<stage>, variable=...)` markers.
- Branched flow with stages reachable via either branch and a final
  stage joined after merge.
- Negative cases captured: missing stage, out-of-order, branch skips a
  required stage via early return.

**Important caveat**
- The evaluator inspects the **target's** AST for `flow(...)` markers;
  the reference describes the *expected* order/membership. A target
  that drops the markers fails with `missing_stages` even when its
  control flow is structurally correct. Targets must repeat the
  `__archtest__: Annotated[None, flow(<stage>, variable=...)]` markers
  alongside the assignments.
- **Runtime alternative (FLW002, `flw002_runtime_flow/`):** give
  `enforce_flow` a `cases=` list and run with `--dynamic`. The reference is
  executed to record which of the project's functions each stage calls, and
  the target must call them in the same stage order — no markers in the
  target, and no value is ever compared. A stage that calls no project
  function is reported as not checked; each case must take the reference
  through every stage.

---

## DYN001 — `forbid_runtime_calls`, `require_runtime_calls`

**Capabilities**
- Calls the matched target with the reference's cases in a separate
  interpreter, only with `--dynamic`, and records every call that code of the
  target's module makes into another module.
- Catches layer bypasses that the static import graph cannot see because the
  dependency arrives as an injected object: a controller reading
  `service.repository` directly.
- `require_runtime_calls` catches work done in place instead of delegated.
- A target with different results but the same layering passes
  (`target_pass_other_pricing`): results are never compared.

**Notes**
- Only direct calls count; the service calling the repository is the
  service's business.
- Without `--dynamic` every rule is `SKIPPED`, so the `target_fail_*`
  verdicts hold only for dynamic runs.
- Cases must reach the code paths whose structure matters.

---

## DYN001 — `enforce_reference_calls` (`dyn001_reference_calls/`)

**Capabilities**
- Runs the reference from the marked entry point and records every call
  between two of its modules; the target may only use those edges, and with
  `require_all` must use all of them.
- One marker covers a whole layered design, including violations two layers
  below the marked function (`notifier -> repository`).
- Different results with the same call graph pass.

**Notes**
- Edges only: which function of a module is called, and how often, is not
  compared.
- Edges into the standard library are not part of the graph.

---

## DYN002 — `forbid_runtime_imports`

**Capabilities**
- Imports the target module in a child interpreter and records every import
  its code performs, including `importlib.import_module` and `__import__`
  with computed names that the static `forbid_imports` cannot follow.
- `allow` exempts submodules under a forbidden prefix.
- A module imported lazily inside a function and then used is caught by
  `forbid_runtime_calls` on that function (`target_fail_lazy_import`).

**Notes**
- Only imports executed from files under the target root count; the
  standard library's own imports are ignored.
- Code paths that the import does not run are not observed.

---

## DYN003 — `forbid_foreign_writes`

**Capabilities**
- While the target runs, every attribute assignment on an instance of a class
  from the analysed project is attributed to the code that made it; anything
  other than the class's own methods is a violation.
- Catches writes hidden in module-level helpers (`target_fail_helper_write`).
- A different order of operations passes as long as encapsulation holds
  (`target_pass_other_order`).

**Notes**
- Mutating a contained object (`account.history.append(...)`) is not an
  attribute assignment and is not seen.

---

## DYN004 — `forbid_runtime_instantiation`

**Capabilities**
- Records which project code creates instances of the project's classes,
  including while a method's instance is built, so a dependency created in
  `__init__` instead of being injected is caught.
- Objects built by the case (`$new`) belong to the caller and do not count;
  creating other domain objects stays allowed.

**Notes**
- Only classes of the analysed project are watched.

---

## DYN005–DYN007 — runtime class rules (`dyn005_runtime_members/`, `dyn006_runtime_classes/`)

**Capabilities**
- Check the object Python builds rather than the class body: attributes
  created by `setattr` in a loop or `__dict__.update` (`dyn005`), abstract
  methods required by a standard-library base, and protocol members bound in
  `__init__` or inherited from a mixin (`dyn006`).
- Each is the runtime counterpart of a static rule (`required_attribute`,
  `does_not_have`, `is_concrete_class`, `is_abstract_class`,
  `implements_protocol`) and closes a gap that rule documents.

**Notes**
- Only the freshly built instance is inspected; members added by later calls
  are not.
- Protocol checks cover presence, callability, and positional arity, not
  annotations.

---

## DYN008 — design patterns (`dyn008_patterns/`)

**Capabilities**
- Singleton, Observer, and Strategy checked by behaviour that defines them:
  identity of two accesses, a probe listener being called (and not after
  unsubscribing), and calls on an injected spy.
- Implementation freedom: `__new__` vs `classmethod` singletons, list vs dict
  listener storage, and different arithmetic around the strategy all pass.

**Notes**
- A spy returns its first argument; code that needs another value may raise
  after delegating, which is reported but not judged.
- A singleton's constructor can still be called directly; Python has no
  private constructors.

---

## Cross-cutting findings

### Silent rule drop on misconfiguration is the biggest ergonomic risk

Across NEG001, an invalid declaration emits a compiler
diagnostic (`compiler_invalid_declaration`,
`compiler_invalid_source_method`, `compiler_invalid_base_reference`)
but the per-target run treats the missing rule as "not present". A
naive reader of `summary.results.status_counts` sees "all OK" and
misses that an entire rule has been dropped.

API004, API005, and API006 are now fixed via the sentinel-rule
pattern (`compiler_invalid_param` emits a FAILED rule result that is
visible in `status_counts`). The generalized helper
`build_invalid_param_sentinel_rule` lives in
`pythonarchtesting.rules.compilation.common`; the same pattern can be
propagated to NEG001 (and to NOM001's
`compiler_invalid_base_reference`) in a follow-up.

**Recommendation**: always run

```
python-arch-test --validate-declarations --source <ref>
```

before treating a green run as conclusive. The showcase's
`findings.md` files explicitly track this for every family.

### `name_match` spelling differs by rule family

| Family                 | Accepted spelling |
|------------------------|-------------------|
| `does_not_have`        | `"alias"`         |
| `require_method_set`   | `"names"`         |
| `require_member_set`   | `"names"`         |

Mixing them emits `compiler_invalid_declaration` and silently drops the
rule.

### Compatible-mode parameter widening interacts with the matcher

When a target legitimately diverges from the source (extra params,
alias names, etc.), the matcher's confidence score may drop below the
matched threshold even though the rule's own verdict logic would have
admitted the change. For `api_signature` rules with
`allow_extra_params=True`, `core/evaluation.py` now re-gates
low-confidence matches at evaluation time when the candidate has the
same name and the divergence is extras-only. Other rule families that
hit the same pattern (e.g. param-rename tolerance) are not yet covered
by similar re-gating; callers can lower matching thresholds in
`[matching]`, but doing so weakens the global match guarantees.

### Single-target Markdown output

`python-arch-test --format markdown --output X.md` for a single-target
run writes the report directly to `X.md` (a file). Multi-target runs
or paths without a `.md` suffix produce a bundle directory containing
`report.md` and a `targets/` subdirectory.
