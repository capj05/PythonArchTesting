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
invalid flag combination, a configuration error, a `--source` or `--target` path
that does not exist, or an output path that cannot be written. Those failures print a single `error: ...` line on stderr and produce no
report. Exit codes `0` and `1` always mean a run completed and was judged.

`SKIPPED` does not fail a target by itself.

Warnings fail a target only when `[report].warnings_as_fail = true`.

The top-level run also gets an aggregate `exit_code`. The aggregate policy comes
from `[report].run_exit_policy`:

- `any_fail` (default): `1` if any target failed
- `all_fail`: `1` only when every target failed
- `threshold`: `1` when the number of failed targets reaches `fail_threshold`

## Read JSON In This Order

Start with:

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
