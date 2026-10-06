# Reusable Workflows Guide

TunaOS provides a suite of organization-wide reusable workflows to standardize CI/CD patterns across repositories. This guide explains which workflow to use for your project and how to integrate each one.

## Workflow Overview

| Workflow | Purpose | Use when... |
|---|---|---|
| `reusable-ci-contract.yml` | Standard CI gate: format check, lint, type-check, tests | Your project has a Justfile with `check` and `test` targets |
| `reusable-lint.yml` | Code quality checks (Markdown, JavaScript, Python linting) | You have documentation or scripts needing syntax/style validation |
| `ste-lint.yml` | Simplified Technical English prose validation | You have README, CONTRIBUTING, or documentation files |
| `reusable-fork-safety.yml` | Block fork PR runs until maintainer approval | Your CI runs privileged QEMU, KVM, or exposes secrets |
| `reusable-first-contributor.yml` | Welcome message and contribution guide for first-time contributors | You want to reduce friction for new contributors |
| `reusable-pr-nudges.yml` | Automated reminders for stalled PRs | You want to keep PR review momentum |
| `reusable-scorecard.yml` | SLSA scorecard security posture tracking | You want supply-chain security visibility |

## Integration patterns

### Pattern 1: Standard CI project

For projects with build/test/lint targets:

```yaml
jobs:
  ci:
    uses: tuna-os/.github/.github/workflows/reusable-ci-contract.yml@main
    with:
      required-checks: 'CI / check,CI / test,CI / build'
```

This workflow requires a `Justfile` with:
- `just check` — fast local checks (format, lint, type-check)
- `just test` — test suite
- `just build` — final artifact or verification

### Pattern 2: Documentation-heavy project

For projects with extensive README or guides, run both lint workflows:

```yaml
jobs:
  lint:
    uses: tuna-os/.github/.github/workflows/reusable-lint.yml@main

  ste:
    uses: tuna-os/.github/.github/workflows/ste-lint.yml@main
    with:
      budget-file: .ste-budget
```

To seed `.ste-budget` with your current findings, run locally:

```bash
node .github/actions/ste-lint/ste-lint.mjs --summary
```

Commit that number, then ratchet it down as you fix findings. The budget only ever decreases — a gate that fails on day one gets disabled on day two, so seed with the honest current count rather than zero.

### Pattern 3: Flatpak application

For apps publishing to the central tuna-os Flatpak remote:

```yaml
jobs:
  publish-flatpak:
    uses: tuna-os/.github/.github/workflows/publish-flatpak.yml@main
    with:
      app-id: org.tunaos.myapp
      manifest-path: flatpak/org.tunaos.myapp.yml
      repo-name: tuna-os/myapp
      archs: '["x86_64","aarch64"]'
    secrets: inherit
```

See [`.github/actions/publish-flatpak-index`](../actions/publish-flatpak-index/README.md) for details, including how to handle the central index push race condition.

### Pattern 4: Fork safety for privileged CI

When your CI runs QEMU, KVM, or other privileged resources:

```yaml
jobs:
  fork-safety:
    uses: tuna-os/.github/.github/workflows/reusable-fork-safety.yml@main

  qemu-tests:
    needs: fork-safety
    if: always()
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: just qemu-tests
```

This blocks fork PRs from running privileged jobs until a maintainer approves. The protection is enforced at the workflow level, not the job level.

### Pattern 5: Community and engagement

For projects that want first-time contributor guidance and PR momentum tracking:

```yaml
jobs:
  first-contributor:
    uses: tuna-os/.github/.github/workflows/reusable-first-contributor.yml@main

  pr-nudges:
    uses: tuna-os/.github/.github/workflows/reusable-pr-nudges.yml@main
    with:
      stale-days: 7
```

## Secrets and permissions

Most reusable workflows accept `secrets: inherit` to forward organization secrets. Some workflows require specific secrets:

| Workflow | Required secrets | Default scopes |
|---|---|---|
| `publish-flatpak.yml` | `FLATPAK_INDEX_TOKEN` | `packages: write`, `contents: read` |
| `reusable-scorecard.yml` | None | `contents: read` |
| Others | None (optional) | `contents: read` |

Minimize secrets passed to fork PRs — use `if: github.event_name != 'pull_request_target'` or rely on `reusable-fork-safety.yml` to block them.

## Customization

Each workflow accepts inputs for common customizations — see the workflow YAML `on.workflow_call.inputs` section for available options and defaults. Do not fork a workflow; instead:

1. File an issue if you need a new capability
2. Use `with:` inputs to customize behavior
3. Copy only if the use case genuinely requires it (and document why in the issue)

## Related documentation

- [`AGENTS.md`](./AGENTS.md) — technical guide for agent automation and impact of changes to this repo
- [`project-starter`](../project-starter) — curated templates for new projects
- [`docs/OBSERVABILITY.md`](./OBSERVABILITY.md) — observability and telemetry standards
