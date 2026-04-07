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

## Markdown Output

### Single-target Markdown

Single-target Markdown is one report document. If `--output` is omitted, the CLI
prints it to stdout. If `--output` is provided, it writes the report to that
file.

### Multi-target Markdown

Multi-target Markdown writes a bundle and requires `--output` to point to a
directory.

Bundle structure:

- `report.md`: run-level summary and target index
- `targets/<target_id>.md`: one page per target

This is the easiest format for sharing batch results with humans.
