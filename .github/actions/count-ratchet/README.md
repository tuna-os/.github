# count-ratchet

Holds counted metrics at a budget that only goes down. A metric is anything
that a regex or a command can count: `.unwrap()` calls, `#[allow` attributes,
skipped tests, or undated advisory ignores.

## The rules

For each metric, the check fails when:

| Condition | Why |
|---|---|
| count > budget | The change adds what the metric counts. Remove the additions. |
| count < budget | Slack. The error gives the exact new budget. Write it in the same pull request. |
| budget > base-branch budget | A pull request raises the budget. This needs the `ratchet-raise` label. |
| metric removed | The check treats removal as a raise. |

The raise check runs on `pull_request` events only. On `push` and
`merge_group` events, the pull request has already passed it.

Slack fails because a budget with room in it is a budget that nobody holds.
The fix is one edit, and the error states it:

```text
unwrap: 140 < budget 143. Lock in the improvement: set `budget = 140` under [metrics.unwrap] in .ratchet.toml
```

## Usage

```yaml
on:
  pull_request:
    # labeled/unlabeled: adding the raise label must run the check again.
    types: [opened, synchronize, reopened, labeled, unlabeled]
  push:
    branches: [main]

permissions:
  contents: read

jobs:
  ratchet:
    runs-on: ubuntu-24.04
    steps:
      - uses: actions/checkout@v7.0.1
        with:
          persist-credentials: false
          fetch-depth: 0  # the raise check reads origin/<base>
      - uses: tuna-os/.github/.github/actions/count-ratchet@<reviewed-main-sha> # main
```

The action needs Python 3.11 or later on the runner, and no packages. The
`ubuntu-24.04` image and later images have it.

| Input | Default | Meaning |
|---|---|---|
| `config` | `.ratchet.toml` | The budget file. |
| `raise-label` | `ratchet-raise` | The label that lets a budget go up. |
| `base-ref` | the pull request base | The branch for the raise check. |
| `python` | `python3` | The interpreter. |
| `only` | empty | Space-separated metric names. Empty checks all metrics. |

## The budget file

```toml
# Applies to each pattern metric, unless the metric sets its own value.
[defaults]
exclude = ["**/tests/**", "**/benches/**", "**/examples/**", "**/*_test.rs", "**/tests.rs"]

[metrics.unwrap]
description = "non-test .unwrap() calls"
pattern = '\.unwrap\(\)'       # Python regex, multiline; each match counts 1
include = ["**/*.rs"]
exclude-rust-tests = true      # skip #[cfg(test)] modules
budget = 143

[metrics.deny-undated]
description = "cargo-deny ignores without a reason and review date"
command = 'python3 "$RATCHET_ACTION_PATH/checks/deny_review_dates.py" deny.toml'
budget = 0
```

A metric sets `pattern` or `command`, not both, and an integer `budget`.

- **`pattern`** counts the matches in the files that git tracks. Binary
  files do not count.
  - `include` and `exclude` are globs. `**` matches zero or more
    directories. `*` stays in one path segment. A glob without a `/`
    matches the file name at all depths. The default `include` is `**`.
  - `exclude-rust-tests = true` removes the code from the first inline
    `#[cfg(test)] mod name {` to the end of the file. It also skips the
    files that a `#[cfg(test)] mod name;` declaration names.
- **`command`** runs in Bash from the repository root. The last line of
  stdout is the count. The command must exit 0. The log shows the lines
  above the count, so a command can name what it counted.
  `$RATCHET_ACTION_PATH` points at this action, for the helpers in
  [`checks/`](checks/).

`[defaults]` can set `include`, `exclude` and `exclude-rust-tests`. A metric
value replaces the default value. The two lists do not merge.

## Helpers

- [`checks/deny_review_dates.py`](checks/deny_review_dates.py) counts the
  `[advisories] ignore` entries in `deny.toml` that have no `reason` with an
  ISO date. The house form is `reason = "...; review by 2027-01-01"`. A date
  in the past gives a warning, but the helper does not count it. Thus the
  date does not make main fail without a code change.

## Local use

```sh
python3 ratchet.py check                  # count and apply the rules (no raise check)
python3 ratchet.py check --base-ref main  # also compare budgets with origin/main
python3 ratchet.py check --json           # print counts only
python3 ratchet.py tighten                # lower each budget to its count
```

Run the commands from the repository root, with `ratchet.py` from a
checkout of `tuna-os/.github`. `tighten` does not raise a budget.

## Budget files with one number

`ratchet.py number` applies the same rules to a count that another tool
makes, against a file that holds one integer. The
[`ste-lint`](../ste-lint/) action uses it for `.ste-budget` when you set
`ratchet: true`.

## Tests

```sh
python3 .github/actions/count-ratchet/test_ratchet.py
```
