# Reporting

Reports answer two questions:

1. did the run fail
2. which rules or targets caused that failure

The CLI supports `json` and `markdown`.

## Exit Code Meaning

Every run goes through the same execution path. A single `--target` path is
treated as a one-element target list and produces the same JSON schema as a
batch run.

Each target gets its own `exit_code`:

- `0`: no `FAILED` or `ERROR` result triggered failure
- `1`: at least one result failed

The CLI process itself also exits `2` when the run could not start at all — an
invalid flag combination (a non-default `--sandbox` or `--sandbox-memory-mb`
without `--dynamic`, `--dynamic` with `--validate-declarations`, a sandbox that
is not available on this machine), a configuration error, a `--source` or `--target` path
that does not exist, or an output path that cannot be written. Those failures print an `error: ...` line on stderr
(after the usage summary when the flags are wrong) and produce no report.
Exit codes `0` and `1` always mean a run completed and was judged.

### Warnings on stderr

A completed run can still pass without having checked everything. The CLI
then prints, on stderr, one line per kind:

- `warning: N runtime rule result(s) were SKIPPED because --dynamic was not
  given; …`
- `warning: N runtime rule result(s) passed with code or cases left
  unchecked; see details.unverified`
- `warning: N result(s) passed with undecided architecture changes; see
  details.undecided` (an `architecture_entry` comparison its policy could not
  judge)

None of them changes the exit code.

`SKIPPED` does not fail a target by itself.

Warnings fail a target only when `[report].warnings_as_fail = true`.

The top-level run also gets an aggregate `exit_code`. The aggregate policy comes
from `[report].run_exit_policy`:

- `any_fail` (default): `1` if any target failed
- `all_fail`: `1` only when every target failed
- `threshold`: `1` when the number of failed targets reaches `fail_threshold`

## Read JSON In This Order

Start with:

- `run.mode`: `static-only` or `dynamic (sandbox: <mode>)`; read it before
  trusting a pass. In a `static-only` run the runtime rules did not run and
  their results are `SKIPPED` (`details.reason` = `dynamic_checks_disabled`)
- `exit_code`
- `summary.targets_total`
- `summary.targets_failed`
- `targets[*].summary`

These fields matter first:

- `summary`
- `targets[*].summary`
- `results[*].message`
- `results[*].fix_hints`
- `results[*].evidence`
- `results[*].locations`

### JSON fields

- top level: `schema_version` (the string `"2"`), `framework_version`,
  `generated_at`, `exit_code`, `run`, `summary`, `targets`;
- `run`: `mode`, `source_path`, `reference_modules`, `tool_version`,
  `generated_at`, `principle` (only for a task source), and
  `config_snapshot` / `config_fingerprint` (`null` unless
  `[report].include_config_snapshot = true`);
- `summary`: `targets_total`, `targets_failed`, `targets_passed`, and
  `results` with `results_total`, `status_counts`, `severity_counts`,
  `category_counts`, `top_rules` and `top_source_files` (`name`, `count`),
  `timings`, and `unverified_total`;
- `targets[*]`: `target_id`, `display_name`, `target_path`, `source_root`,
  `mode`, `exit_code`, `summary`, `matching` (`matches`, `matching_config`),
  `results`, `artifacts`, `tags`;
- `results[*]`: `result_id`, `rule_id`, `rule_type`, `category`, `status`,
  `severity`, `message`, `fix_hints`, `evidence`, `locations` (`source` and
  `target`: `file`, `line`, `module`, `qualname`, …), `source` and `target`
  (the paired entities), `source_entity_id`, `target_entity_id`,
  `match_status`, `confidence`, `details`, `project_id`, `timing_seconds`,
  `tags`.

## Status vs Severity

These fields mean different things:

- `status`: what happened to the check result
- `severity`: how serious that result is meant to be

Common statuses:

- `OK`: the rule passed
- `FAILED`: the rule failed
- `SKIPPED`: the rule was not evaluated, usually because matching did not
  produce a usable target, or because it is a runtime rule (`DYN*`, `FLW002`)
  and the run had no `--dynamic` (`details.reason` is
  `dynamic_checks_disabled`)
- `ERROR`: the rule could not be evaluated because of the reference, for
  example a runtime rule whose reference did not run (`reference_failed`),
  never reached a flow stage (`reference_misses_stage`), or whose case cannot
  be set up even for the reference (`reference_case_invalid`)

A runtime result also carries `details.reason`: `violation` (or a
rule-specific reason such as `stage_order_mismatch`) when it failed on what
the target did, and `probe_timeout`, `probe_crashed`, `probe_import_error`, or
`case_setup_failed` when the target's code could not be run as the cases ask.
See [dynamic-checks.md](dynamic-checks.md).

Common severities:

- `error`
- `warning`
- `info`

If a result is `SKIPPED`, read `match_status`, `message`, and `details` before
assuming the rule logic is wrong.

## Matching States

The `matching` section explains how the tool paired source entities with target
entities.

Common matching states:

- `matched`: a usable target entity was found
- `low_confidence`: the best candidate was weak
- `ambiguous`: several candidates competed too closely
- `unmatched`: no usable target entity was found

Matching data is most useful when a result says a required target is missing or
when a failure looks surprising.

### Pairing by name

A submission that names its modules differently and rewrites the bodies
loses most of the score, so an entity can stay unpaired although the target
has an obvious counterpart. With `[matching] name_fallback = true` (the
default) two rules then pair it, after an assisted mapping (below) has been
applied:

- `unique_name`: a top-level class or function the scores left without a
  usable candidate is paired with the only top-level target entity of its
  kind and name, when the reference has no other entity of that name. A
  function must accept the reference's positional arguments; a class must
  have every ordinary method the reference's class defines (special methods,
  such as a dataclass's generated `__init__`, are not required), and none of
  them may be paired with another class's methods already;
- `member_of_paired_class`: a method the scores did not match is paired with
  the method of the same name and a compatible signature of the target class
  its class was paired with. Inside a paired class the name outweighs a weak
  guess of the scores (`low_confidence`, `ambiguous`).

Modules and methods are never paired by name alone (a renamed module needs a
mapping for the markers declared on it; the only method of a name may be a
base class's). Otherwise the scores keep the last word: a match is never
replaced or taken, an entity whose weak best candidate is another target
keeps it, and a target two unmatched entities score best for goes to the
higher score. A pair made by name lists its target first among the
candidates with the score the matching gave it (0 when none) and the rule
among its reasons; `propose_mapping` lists these pairs as
`paired_by_name`, and a mapping for one of them replaces it. Measured on the
project's example targets whose correct pairing is known, the rules made no
wrong pair; none of those targets is adversarial
([matching_weights](../example/matching_weights/README.md)).

### Assisted pairing

A submission organised differently from the reference (other module names,
rewritten bodies) can leave entities unpaired, and every rule on them then
reports `required_target_missing`. `--mapping FILE` pairs them explicitly:

```json
{"pairs": {"controller": "handler", "models.Order": "order.Order"}}
```

or per target, `{"targets": {"<target id>": {"pairs": {...}}}}`; a target's
pairs add to the common `pairs` and win over them, and a target id that names
no target of the run is an error. Names are
`module` or `module.Qual.name` (the root package is `__init__`); a pair of
modules pairs the entities with the same qualified name inside them, except
those the mapping pairs explicitly (`module.name`), which keep that pair. Every
pair is checked before it is used: both entities must exist and be of the same
kind, a function of the target must accept the reference's positional
arguments, and an entity the matching paired on its own keeps its pair. An
applied pair carries the reason `assisted_mapping` in the match, a refused one
`assisted_mapping_rejected` with why. The MCP tool `propose_mapping` lists the
unpaired entities of one target with their best candidates, as material for a
proposal ([mcp.md](mcp.md)).

The signature check counts positional parameters and required keyword-only
ones; it does not know decorators, so a reference method paired with a
target `@staticmethod` of the same arity is refused (the reference's
`self` is counted on one side only). A dotted name that means two entities
(a submodule `a/b.py` and a class `b` in `a/__init__.py`, or a property
with a setter) is refused as ambiguous; pair the module instead.

## Result Rows

For each result row, focus on:

- `rule_id`: which rule fired
- `status`: pass, fail, or skipped
- `severity`: error, warning, or info
- `message`: short explanation
- `fix_hints`: actionable next steps
- `locations`: source and target file/line references
- `evidence`: structured supporting data

Typical workflow:

1. use `summary` to find the failing target
2. open that target's failed rows
3. read `message`
4. use `fix_hints`
5. inspect `evidence` only if the message is not enough

### Runtime facts

A failed `forbid_runtime_calls`, `require_runtime_calls`,
`forbid_foreign_writes`, `forbid_runtime_instantiation` or
`require_runtime_delegation` result lists its violations twice, and so does
a failed static `forbid_private_access`, `subclass_of` or
`is_abstract_class` (whose facts have no `case`). `details.violations`
holds them as English sentences, and `details.facts` holds them as data, so a
client can phrase the explanation in its own words and language. The two lists
have the same length and order: `facts[i]` is `violations[i]`. A passing result
has neither list, and neither has a failed result that ends before a case runs
(probe timeout, case setup failure, target-kind mismatch); its `reason` and
`summary` say why. Every fact has `kind` and `case` (the index of the case it
was seen in):

| `kind` | Other keys |
|---|---|
| `call` | `caller` and `callee` (`"module:qualname"`), `file` and `line` where the call was made, `via` (the code a transitive call went through, `"module:qualname"`, outermost first; empty for a direct call), `origin_line` (the line of `caller` the transitive call's detour starts at; `null` for a direct call) |
| `missing_call` | `module` (the target's module no call went into), `reference_module` (the required module as the marker names it), `raised` (the exception the case stopped at, or `null`) |
| `write` | `change` (`assigned`, `mutated`, `deleted` or `bypassed`), `writer` (`"module:qualname"`), `class`, `attribute`, `file`, `line` |
| `instance` | `creator` (`"module:qualname"`, the target's code the object is charged to), `class` (`"module:Class"`), `file` and `line` where the object was built, `via` (the code a transitive instance was built through, outermost first; empty otherwise) |
| `missing_delegation` | `caller` (the target, `"module:qualname"`), `expected` (the spy, or `"spy.member"`), `raised` (the exception the case stopped at, or `null`) |
| `read` (static) | `reader` (`"module:qualname"`), `class`, `attribute`, `file`, `line` |
| `not_subclass` (static) | `class` and `expected_base` (`"module:Class"`), `file`, `line` of the class |
| `not_abstract` (static) | `class` (`"module:Class"`), `concrete_methods` (what it defines without an abstract decorator), `file`, `line` |

For a transitive call `caller` is the target's code the call is charged to,
`origin_line` is the line of it that starts the detour, and `file` and `line`
belong to the last step of `via`. `file` is relative to the target root, and
`null` for code generated from a string, such as a dataclass `__init__`.

Module and function names in `caller`, `callee`, `via`, `writer` and `class`
are the target's own. For `missing_call`, `module` is the target's name of the
required module when the matching step mapped it to a target module of another
name, and `reference_module` is the name the marker uses; without such a
mapping both hold the same name. The English sentences in `violations` keep the
reference's name.

## Markdown Output

Markdown output always writes a bundle and requires `--output` to point to a
directory:

```bash
python-arch-test --source example/checkout_assignment/reference \
  --target example/checkout_assignment/assignments/target3 \
  --format markdown --output example/checkout_assignment/reports/report_md
```

Bundle structure:

- `report.md`: run-level summary and target index
- `targets/<target_id>.md`: one page per target

This is the easiest format for sharing batch results with humans.

### Detail Level

The `[report].markdown_detail` config setting controls how much each target
page contains. Allowed values:

- `summary`: metadata, summary counts, results table
- `verbose` (default): adds the matching summary section (totals, matched,
  low confidence, ambiguous, unmatched)
- `debug`: adds the per-source matching candidates breakdown — this content
  is also available in the JSON report under `targets[*].matching.matches[*]`,
  so prefer `verbose` for shared markdown and use the JSON when investigating
  matching itself.

At `verbose` and `debug` the run-level `report.md` also includes status,
severity, and category counts plus the top-N rules and source files by
violation count, derived from the same aggregates that appear in the JSON
`summary.results` block.

With `architecture_entry` results, target pages at `verbose` and `debug`
have an **Architecture** section (counts, edges, dependency matrices,
informative module metrics, static vs runtime), and `report.md` ranks the
edges several targets share (**Architecture Across Targets**); see
[architecture_entry](markers/architecture_entry.md#what-it-checks).
