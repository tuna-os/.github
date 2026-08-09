# TunaOS project starter

A curated, copyable baseline for TunaOS projects. It distils the practices that recur across the organisation while keeping heavy integrations opt-in.

## Start a project

1. Create the repository and copy this directory's contents to its root.
2. Replace every `<…>` placeholder.
3. Keep the targets you implement in `Justfile`; remove unused workflow templates.
4. Enable branch protection with `CI / required-checks` as the required check.
5. Enable Renovate for the repository.

## What is included

| Component | Purpose | Source pattern |
| --- | --- | --- |
| `Justfile` | One discoverable local command surface | tunaOS, bootc-migrate, wootc |
| `renovate.json` | Automated dependency, action, digest, and pin updates | organisation default, tunaOS |
| `ci.yml` | Least-privilege checks, cancellation, and a branch-protection sentinel | bootc-migrate |
| `flatpak-remote.yml` | Build an OCI Flatpak and update a hosted remote index | tuna-os/docs |
| `docs-artifacts.yml` | Turn validated screenshots or walkthroughs into versioned docs | tunaOS → docs |

## Principles

- Make the normal path obvious: `just check` should reproduce CI locally.
- Prefer narrow, independently observable jobs. Add a single required sentinel only after it depends on every real gate.
- Pin build inputs where reproducibility matters; let Renovate maintain pins. Debounce fast-moving image digests rather than burning CI on every upstream change.
- Treat generated documentation as a release artifact: capture it from the real product, preserve artifacts on failures, and commit only after validation.
- Use least privilege by default. Never expose secrets or privileged runners to untrusted fork pull requests.
- Make automation idempotent and explain its operational constraints beside the code.
- Keep heavyweight E2E scheduled or explicitly dispatched; make PR gates proportional to risk.

Read [ADOPTING.md](docs/ADOPTING.md) before enabling a profile. These are templates, not a mandate: remove anything that does not serve the project.
