# Reporting

Reports answer two questions:

1. did the run fail
2. which rules or targets caused that failure

The CLI supports `json` and `markdown`.

## Exit Code Meaning

### Single-target runs

- exit code `0`: no `FAILED` or `ERROR` result triggered failure
- exit code `1`: at least one result failed

`SKIPPED` does not fail the run by itself.

Warnings fail the run only when `[report].warnings_as_fail = true`.

### Multi-target runs

Each target gets its own `exit_code`, and the top-level run also gets an
aggregate `exit_code`.

The aggregate policy comes from `[report].multi_target_exit_policy`:

- `any_fail`
- `all_fail`
- `threshold`

When you use `threshold`, `fail_threshold` decides how many failed targets are
required before the full run exits with `1`.

## JSON Compatibility

JSON report semantics remain unchanged by the reporting update described in this
document.

- JSON output stays on the current schema contract.
- JSON read order stays the same.
- Markdown mode definitions in this document do not change JSON structure,
  fields, or meaning.
- Any future mode selection added in code must affect Markdown rendering only,
  unless explicitly documented otherwise in a later phase.

## Read JSON In This Order

### Single-target

Start with:

- `exit_code`
- `summary`
- `results`

### Multi-target

Start with:

- `exit_code`
- `summary.targets_total`
- `summary.targets_failed`
- `summary.results`
- `targets[*].summary`

These fields matter first:

- `summary`
- `targets[*].summary`
- `results[*].message`
- `results[*].fix_hints`
- `results[*].evidence`
- `results[*].locations`

## Status vs Severity

These fields mean different things:

- `status`: what happened to the check result
- `severity`: how serious that result is meant to be

Common statuses:

- `OK`: the rule passed
- `FAILED`: the rule failed
- `SKIPPED`: the rule was not evaluated, usually because matching did not
  produce a usable target

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

## Markdown Product Contract

This section is the canonical source of truth for Markdown reporting behavior.
The current implementation follows this contract for Markdown rendering only.

### Mode Definitions

The approved Markdown modes are:

- `standard`: default user-facing summary; aggregated, run-first, and optimized
  for quick scanning
- `verbose`: user-facing remediation detail; additive over `standard`
- `debug`: developer-facing diagnostics; additive over `verbose`

Select a mode with `--markdown-mode standard|verbose|debug`. Defaults to
`standard`.

Normative rules:

- `standard` answers: did the run fail, which targets have issues, and which
  rules are recurring hotspots
- `verbose` keeps the same triage-first run overview as `standard`, but adds
  linked target pages for fixing issues
- `debug` keeps the `verbose` run overview and target pages, then adds
  diagnostic appendices on target pages
- `debug` is the only mode where diagnostic-heavy content is allowed by default

#### Standard mode (default)

- Audience: quick CI scan
- Default: yes (when `--markdown-mode` is omitted)
- Shows: verdict, summary counts, short issue summary, optional warnings-only
  summary, optional OK summary, rule hotspots
- Forbidden: Matching Debug, Raw Evidence, Full Result Table, Issue Summary by
  Rule, Rule Details, Compact Passed Summary
- Multi-target: `report.md` is the only user-facing page

#### Verbose mode

- Audience: developer fixing failures
- Default: no
- Shows: the same run-level triage sections as `standard`, plus linked
  target pages with `Issue Summary by Rule`, `Rule Details`, `Warnings`, and
  `Compact Passed Summary`
- Forbidden: Matching Debug, Raw Evidence as primary sections
- Multi-target: adds target pages at `targets/<target_id>.md`

#### Debug mode

- Audience: developer investigating unexpected results
- Default: no
- Shows: the same run-level triage sections as `verbose`, plus target-page
  appendices for Matching Debug, Raw Evidence, Full Result Table, and optional
  Internal Diagnostics
- Multi-target: same bundle shape as Verbose with debug appendices on target pages

### Markdown Output Topology

#### Single-target Markdown

Single-target Markdown remains one report document in all modes.

- `standard`: exactly one report document only
- `verbose`: exactly one report document with target-detail sections embedded
  inline
- `debug`: one report document with the `verbose` structure plus debug
  appendices inline
- no bundle directory is introduced in any single-target mode
- no `targets/` subdirectory is introduced in any single-target mode
- no separate target page is allowed for single-target output
- single-target Markdown remains suitable for stdout output

#### Multi-target Markdown

Multi-target Markdown always uses `report.md` as the bundle root. Target pages
at `targets/<target_id>.md` exist only in `verbose` and `debug`.

Mode-specific contract:

- `standard`: `report.md` remains the run-level entry point and the only
  user-facing page in the default contract
- `verbose`: `report.md` plus `targets/<target_id>.md`
- `debug`: same bundle shape as `verbose`

This phase does not approve any alternative directory layout or collapsing
multi-target Markdown into a single flat file by default.

#### Topology Parity Rule

Markdown modes must preserve the same semantic reading order across
single-target and multi-target runs, but they do not need to preserve the same
file count.

- single-target uses inline detail because there is only one target
- multi-target `standard` keeps all scanning content on `report.md`
- multi-target `verbose` and `debug` add target pages because there are
  multiple navigable units

#### Forbidden Topology Changes

Single-target Markdown must not:

- generate `report.md` plus `targets/<target_id>.md` as a synthetic bundle
- require an output directory for Markdown generation
- create a `targets/` directory only for parity with multi-target runs
- split `verbose` or `debug` output across multiple files in this phase

Multi-target Markdown must not:

- collapse `verbose` or `debug` output into one monolithic Markdown page by
  default
- rename bundle roots away from `report.md` and `targets/<target_id>.md` in
  this phase

#### Topology Examples

Single-target `verbose` example:

- `student_a_report.md`
- inline verdict
- inline issue summary by rule
- inline rule details
- inline warnings
- inline compact passed summary

Single-target `debug` example:

- `student_a_report.md`
- all `verbose` content inline
- inline matching debug appendices
- inline raw evidence appendices
- inline full result table appendices

Multi-target `verbose` example:

- `report.md`
- `targets/student_a.md`
- `targets/student_b.md`

Multi-target `debug` example:

- `report.md`
- `targets/student_a.md`
- `targets/student_b.md`
- target pages include debug appendices without changing bundle shape

### Reading Order

#### Standard

1. verdict
2. targets with issues
3. warnings-only targets
4. OK targets
5. rule hotspots
6. short navigation or short per-target summaries

#### Verbose

1. run verdict
2. failing targets
3. navigation to target detail
4. target verdict
5. issue summary by rule
6. rule detail blocks
7. warnings
8. compact passed summary

#### Debug

1. the full `verbose` reading order
2. matching debug
3. raw evidence
4. full result table
5. internal diagnostics

### Section Vocabulary

These names are canonical for user-visible Markdown sections.

| Section | Level | Meaning |
| --- | --- | --- |
| `Verdict` | run, target | The pass/fail outcome that readers should interpret first. |
| `At a glance` | run | Compact metrics table for multi-target `standard` triage. |
| `Projects with issues` | run | Failing projects surfaced first in triage-first multi-target run indexes. |
| `Common failure causes` | run | Non-OK rule hotspots ranked for triage-first multi-target run indexes. |
| `Projects with warnings only` | run | Warning-only projects separated from failing projects in triage-first multi-target run indexes. |
| `Passed projects` | run | Collapsed passed-project summary used by triage-first multi-target run indexes. |
| `Run metadata` | run | Low-priority generated/framework/source metadata placed at the end of triage-first multi-target run indexes. |
| `Warnings Only` | run, target | Targets or target-local findings with warnings but no failing outcome. |
| `OK Targets` | run | Targets with no actionable problems in compact single-target summaries or older contracts. |
| `Rule Hotspots` | run, target | Recurring or dominant failing rules worth prioritizing. |
| `Short Issue Summary` | target | Compact non-remediation summary of the failing rules shown in single-target `standard`. |
| `Short Per-Target Summaries` | run | Compact summaries used for scanning and navigation when a multi-target run index embeds per-target triage rows. |
| `Navigation` | run | Links or navigational hints that move readers to richer detail. |
| `Issue Summary by Rule` | target | Grouped summary of target issues organized by rule. |
| `Rule Details` | target | Rule-centered detail blocks used for remediation. |
| `Compact Passed Summary` | target | Brief summary of what passed without listing every passed row. |
| `Matching Debug` | debug | Diagnostic matching detail intended for investigation, not normal reading. |
| `Raw Evidence` | debug | Evidence dumps that support deep investigation. |
| `Full Result Table` | debug | Flat row listing of all results for exhaustive inspection. |
| `Internal Diagnostics` | debug | Additional renderer or engine diagnostics intended for developers. |

### Forbidden Content Rules

`standard` must not include:

- matching debug
- raw evidence dumps
- full result tables
- passed-result row listings
- target pages in multi-target output

`verbose` must not include:

- full matching candidate matrices as primary sections
- raw evidence dumps as primary sections
- full result tables as primary sections
- diagnostic-first ordering

`debug` may include all diagnostic material, but it must still preserve the
`verbose` reader journey before appendices.

### Content Matrix

#### Single-target

| Section | Standard | Verbose | Debug |
| --- | --- | --- | --- |
| Report title and generated metadata | Required | Required | Required |
| Verdict | Required | Required | Required |
| Run or target summary counts | Required | Required | Required |
| `Warnings Only` | Optional | Optional | Optional |
| `OK Targets` style summary | Optional | Optional | Optional |
| `Rule Hotspots` | Required if data is available | Required if data is available | Required if data is available |
| Short issue summary | Required | Forbidden | Forbidden |
| `Issue Summary by Rule` | Forbidden | Required | Required |
| `Rule Details` | Forbidden | Required | Required |
| Standalone `Warnings` section | Forbidden unless needed in the summary | Required if warnings exist | Required if warnings exist |
| `Compact Passed Summary` | Forbidden | Required | Required |
| Matching summary counts | Forbidden | Optional only when needed for interpretation | Optional |
| `Matching Debug` | Forbidden | Forbidden | Required |
| `Raw Evidence` | Forbidden | Forbidden | Required |
| `Full Result Table` | Forbidden | Forbidden | Required |
| `Internal Diagnostics` | Forbidden | Forbidden | Optional |

#### Multi-target `report.md`

All multi-target Markdown modes use a triage-first `report.md` overview: verdict
banner, `At a glance`, `Projects with issues`, `Common failure causes`,
optional `Projects with warnings only`, collapsed `Passed projects`, and a
`Run metadata` footer. `standard` keeps that overview as the only user-facing
page. `verbose` and `debug` retain the bundle structure with `report.md` plus
`targets/<target>.md`.

| Section | Standard | Verbose | Debug |
| --- | --- | --- | --- |
| Report title and generated metadata | Required, but metadata moves to `Run metadata` footer | Required | Required |
| Verdict | Required | Required | Required |
| `At a glance` | Required | Required | Required |
| `Projects with issues` | Required | Required | Required |
| `Common failure causes` | Required if non-OK hotspot data is available | Required if non-OK hotspot data is available | Required if non-OK hotspot data is available |
| `Projects with warnings only` | Required if present | Required if present | Required if present |
| `Passed projects` | Required if any targets are `OK` | Required if any targets are `OK` | Required if any targets are `OK` |
| `Run metadata` | Required | Required | Required |
| `Targets With Issues` | Forbidden | Forbidden | Forbidden |
| `Warnings Only` | Forbidden | Forbidden | Forbidden |
| `OK Targets` | Forbidden | Forbidden | Forbidden |
| `Rule Hotspots` | Forbidden | Forbidden | Forbidden |
| `Short Per-Target Summaries` | Forbidden | Forbidden as a standalone section | Forbidden as a standalone section |
| `Navigation` links to target pages | Forbidden | Required | Required |
| Flat target table in current form | Forbidden unless redesigned to fit this contract | Forbidden unless redesigned to fit this contract | Optional |
| `Matching Debug` | Forbidden | Forbidden | Forbidden at run-index level by default |
| `Raw Evidence` | Forbidden | Forbidden | Forbidden at run-index level by default |
| `Full Result Table` | Forbidden | Forbidden | Forbidden at run-index level by default |

#### Multi-target `targets/<target>.md`

| Section | Standard | Verbose | Debug |
| --- | --- | --- | --- |
| Target page existence | Forbidden | Required | Required |
| `Verdict` | N/A | Required | Required |
| Metadata block as primary section | Forbidden | Optional, compact only | Optional |
| `Issue Summary by Rule` | N/A | Required | Required |
| `Rule Details` | N/A | Required | Required |
| `Warnings` | N/A | Required if present | Required if present |
| `Compact Passed Summary` | N/A | Required | Required |
| Matching summary counts | N/A | Optional only when needed for interpretation | Optional |
| `Matching Debug` | N/A | Forbidden | Required |
| `Raw Evidence` | N/A | Forbidden | Required |
| `Full Result Table` | N/A | Forbidden | Required |
| `Internal Diagnostics` | N/A | Forbidden | Optional |

### Out Of Scope For Phase 1

This document does not approve implementation work in Phase 1.

Specifically out of scope:

- renderer changes
- new config keys
- new CLI flags
- IR or schema changes
- aggregation redesign
- changes to JSON output

Later phases may implement this contract, but they must not reopen the product
semantics defined here unless the contract itself is revised.
