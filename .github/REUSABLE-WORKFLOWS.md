# Reusable Workflows Catalog

This document catalogs the shared reusable workflows available to all tuna-os repositories. Each workflow is a composable, parameterized GitHub Actions workflow hosted in `.github/workflows/` that repositories call via `uses:` in their own workflows.

## Quick Start

To use a reusable workflow in your repository:

```yaml
name: Your Workflow
on: pull_request  # or whatever trigger you need

jobs:
  example:
    uses: tuna-os/.github/.github/workflows/reusable-example@main
    with:
      param-name: param-value
```

Pin workflows to `@main` (live tracking) or a specific commit/tag for stability. All workflows list their inputs and outputs explicitly.

---

## Workflows by Category

### Contributor Experience

#### `reusable-first-contributor.yml`

**Purpose**: Automatically greet and welcome first-time contributors when they open a PR or issue.

**Trigger**: Fires on `pull_request` and `issues` events.

**Inputs**:
- `pr_message` (string, optional): Custom message for first-time PR authors. Defaults to a welcome message citing DCO sign-off and PR guidelines.
- `issue_message` (string, optional): Custom message for first-time issue authors. Defaults to a welcome message.

**Behavior**:
- Detects whether it's a first-time contributor in **this repository** (not org-wide).
- Skips greetings for bots and automated accounts (dependabot, github-actions, etc.).
- Only posts one greeting per author (idempotent).

**Example usage**:

```yaml
jobs:
  greeting:
    uses: tuna-os/.github/.github/workflows/reusable-first-contributor@main
    with:
      pr_message: |
        Welcome aboard! 🎉
        Please ensure all commits are signed: git commit -s
```

---

### Code Quality & Linting

#### `reusable-lint.yml`

**Purpose**: Run static analysis on shell scripts, YAML, JSON, GitHub Actions workflows, and Justfiles.

**Trigger**: Called on-demand or from another workflow.

**Inputs**:
- `checks` (string, optional): JSON array of checks to run. Defaults to `["shellcheck", "yamllint", "json-validate", "actionlint", "justfmt"]`.

**Available checks**:
- `shellcheck` — Shell script linting (excludes SC1091, SC2114 by default).
- `yamllint` — YAML validation (reads `.yamllint.yml` if present).
- `json-validate` — Validates JSON syntax.
- `actionlint` — GitHub Actions workflow validation (non-fatal).
- `justfmt` — Justfile formatting (skipped if no Justfile present).

**Exclusions** (automatic):
- `.build/`, `vendor/`, `_upstream-snapshots/` directories.

**Example usage**:

```yaml
jobs:
  lint:
    uses: tuna-os/.github/.github/workflows/reusable-lint@main
    with:
      checks: '["shellcheck", "yamllint"]'
```

---

### Pull Request Guidance

#### `reusable-pr-nudges.yml`

**Purpose**: Post advisory reminders on pull requests based on files changed, without failing the PR.

**Trigger**: Runs on `pull_request` events.

**Behavior**:
- Skips draft PRs and dependency bot updates (Renovate, Dependabot).
- Runs a caller-supplied script (`.github/scripts/pr-nudges.sh` by default) that reads the changed file list.
- Posts reminders via step summary, annotations, and a PR comment (if permissions allow).
- **Never fails** — violations are advisory only.

**Inputs**:
- `script-path` (string, optional): Path to the nudge script in your repo. Default: `.github/scripts/pr-nudges.sh`.

**Your nudge script**:
- Receives the list of changed file paths on stdin (one per line).
- Called with `--deliver` flag.
- Can output structured reminders (exact format varies by repo).

**Example usage**:

```yaml
jobs:
  nudges:
    uses: tuna-os/.github/.github/workflows/reusable-pr-nudges@main
    with:
      script-path: .github/scripts/custom-nudges.sh
```

---

### Issue Management

#### `reusable-add-help-wanted.yml`

**Purpose**: Automatically label unassigned issues as "help wanted" when they meet criteria.

**Trigger**: Fires on `issues` events (when labeled, opened, edited, etc.).

**Behavior**:
- Checks if an issue is unassigned.
- If unassigned and no "help wanted" or "good first issue" label exists, adds "help wanted".
- Continues on error (does not fail the workflow).

**No inputs or customization**.

**Example usage**:

```yaml
jobs:
  label:
    uses: tuna-os/.github/.github/workflows/reusable-add-help-wanted@main
```

---

### CI/CD Validation

#### `reusable-ci-contract.yml`

**Purpose**: Verify that every "green criterion" in `.github/green-criteria.yml` is:
1. Declared in a reachable workflow.
2. Backed by real jobs and steps.
3. Satisfies freshness SLAs (not stale).

**Trigger**: Called on-demand or from another workflow.

**Inputs**:
- `criteria-path` (string, optional): Path to criteria file. Default: `.github/green-criteria.yml`.
- `workflows-dir` (string, optional): Directory containing workflows. Default: `.github/workflows`.
- `python-version` (string, optional): Python version. Default: `"3.11"`.

**Prerequisites**:
Your repo must have a `.github/green-criteria.yml` file defining your CI contract. Structure:

```yaml
criteria:
  - id: "build-and-test"
    gates:
      - workflow: .github/workflows/ci.yml
        jobs:
          build: "Build step"
          test: "Test step"
    asserted_by: "ci.yml builds and tests on every PR"
    freshness_sla_days: 30
    enforcement: blocking
```

**Example usage**:

```yaml
jobs:
  verify-contract:
    uses: tuna-os/.github/.github/workflows/reusable-ci-contract@main
    with:
      criteria-path: .github/green-criteria.yml
```

---

#### `reusable-fork-safety.yml`

**Purpose**: Statically verify that workflows triggered on `pull_request` events (from forks) are safe.

**Trigger**: Called on-demand or from another workflow.

**Inputs**:
- `workflows-dir` (string, optional): Directory containing workflows. Default: `.github/workflows`.
- `python-version` (string, optional): Python version. Default: `"3.11"`.

**Checks**:
1. All `pull_request` workflows declare explicit `permissions:`.
2. No use of `pull_request_target` (which exposes secrets to untrusted code).
3. Steps that write data or reference secrets are guarded by fork-aware conditions (e.g., `github.event_name != 'pull_request'`).

**Why it matters**:
On a `pull_request` event from a fork:
- `GITHUB_TOKEN` is read-only.
- All repository secrets are empty.
- Unguarded write operations or secret references are caught.

**Example usage**:

```yaml
jobs:
  fork-check:
    uses: tuna-os/.github/.github/workflows/reusable-fork-safety@main
```

---

### Security Scanning

#### `reusable-scorecard.yml`

**Purpose**: Run OSSF Scorecard to assess repository security posture.

**Trigger**: Called on-demand or from another workflow.

**No inputs or customization** (scorecard runs with default settings).

**Output**:
- SARIF report uploaded to the repository's security tab.
- Results also logged to the workflow run.

**Example usage**:

```yaml
jobs:
  scorecard:
    uses: tuna-os/.github/.github/workflows/reusable-scorecard@main
```

---

## Integration Patterns

### Pattern 1: Mandatory Checks (Pull Request)

Run linting and fork-safety checks on every PR:

```yaml
name: PR Checks
on: pull_request

jobs:
  lint:
    uses: tuna-os/.github/.github/workflows/reusable-lint@main

  fork-safety:
    uses: tuna-os/.github/.github/workflows/reusable-fork-safety@main

  nudges:
    uses: tuna-os/.github/.github/workflows/reusable-pr-nudges@main
    if: always()  # Run nudges even if checks fail
```

### Pattern 2: Welcome New Contributors + Guidance

On PR and issues:

```yaml
name: Community
on:
  pull_request:
  issues:

jobs:
  welcome:
    uses: tuna-os/.github/.github/workflows/reusable-first-contributor@main

  label:
    uses: tuna-os/.github/.github/workflows/reusable-add-help-wanted@main
```

### Pattern 3: Enforce CI Contract

On every push and PR, verify CI contract and scorecard:

```yaml
name: Contracts
on:
  push:
    branches: [main]
  pull_request:

jobs:
  ci-contract:
    uses: tuna-os/.github/.github/workflows/reusable-ci-contract@main

  scorecard:
    uses: tuna-os/.github/.github/workflows/reusable-scorecard@main
    if: github.event_name == 'push'
```

---

## Common Customizations

### Custom PR Welcome Message

Override the default first-contributor message:

```yaml
jobs:
  welcome:
    uses: tuna-os/.github/.github/workflows/reusable-first-contributor@main
    with:
      pr_message: |
        Thanks for your PR! 🎉
        - Sign commits: `git commit -s`
        - See CONTRIBUTING.md for guidelines
```

### Custom Lint Rules

Run a subset of linters:

```yaml
jobs:
  lint:
    uses: tuna-os/.github/.github/workflows/reusable-lint@main
    with:
      checks: '["shellcheck", "json-validate"]'
```

### Custom PR Nudge Script

Point to a repository-specific nudge script:

```yaml
jobs:
  nudges:
    uses: tuna-os/.github/.github/workflows/reusable-pr-nudges@main
    with:
      script-path: .github/scripts/my-custom-nudges.sh
```

---

## Troubleshooting

### Workflow Not Found

**Error**: `Error: The workflow is not accessible from this repository`

**Solution**:
- Verify the workflow exists in `tuna-os/.github/.github/workflows/`.
- Use the full path: `tuna-os/.github/.github/workflows/reusable-name@main`.
- Check your repo has read access to the `.github` repository.

### Permission Denied

**Error**: Steps fail with permission errors (e.g., unable to comment on PR).

**Solution**:
- Check your repo's workflow permissions: Settings → Actions → General → Workflow permissions.
- For PR operations, the workflow needs `pull-requests: write` (usually set automatically).
- Reusable workflows inherit the caller's permissions by default.

### Lint Finds Issues But Doesn't Fail

**Solution**: This is expected. Many linters (e.g., `actionlint`) are advisory. To make them fatal, set `fail-fast: true` in your caller workflow.

---

## Related Documentation

- **CI Contract Schema**: See `.github/green-criteria.yml` examples in any repo using reusable-ci-contract.yml.
- **Fork Safety**: GitHub's [fork execution docs](https://docs.github.com/en/actions/using-workflows/about-workflows#permissions-for-pull-requests).
- **Org Practices**: See `AGENTS.md` for broader contributor automation guidance.
