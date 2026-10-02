# Runbook: `publish-flatpak.yml` partial failure

## Scope

Applies to any caller of the reusable workflow at
`.github/workflows/publish-flatpak.yml` and the
`publish-flatpak-index` composite action it calls. The pipeline has three
independently-failable write operations per release:

1. Push the OCI image to the registry (`ghcr.io/<repo-name>`), once per arch,
   each with a `latest-<arch>` tag and (on a tag push) a `<version>-<arch>`
   tag, plus an unqualified `:latest` pointing at the primary arch.
2. Update the central index (`tuna-os/docs`'s
   `static/flatpak/index/static`), once per arch, via a separate
   `publish-flatpak-index` step.
3. On `attach-bundles: true` and a tag push, attach built `.flatpak` bundles
   to the GitHub release.

There is no transaction across these steps and no automatic rollback. A
failure partway through leaves whichever writes already landed in place.

## How to tell something is in a partial state

Compare, for the run in question:

- The run's **Push OCI to registry** step log — which arches it reported as
  pushed, and whether it reached the final `:latest` copy line.
- The run's **Update central index — x86_64** / **— aarch64** steps —
  success, "No index changes," or failure. Each is independent; one can
  succeed while the other fails.
- `git log -- static/flatpak/index/static` in `tuna-os/docs`, filtered to
  `chore(flatpak): update <repo-name> OCI index` commits, for whether the
  index commit for this run's arch(es) actually landed.
- `skopeo inspect docker://ghcr.io/<repo-name>:latest-<arch>` (and
  `:<version>-<arch>` if this was a tag push) against what the registry
  actually serves, for whether that arch's image is really there.

The combination that matters operationally: **registry has the image, index
does not point at it** (or points at a stale digest) is a user-visible break
— installs/updates for that app silently keep serving the old build. The
reverse (index updated, registry push failed) fails loudly in the same run
and is self-evident from the red step.

## Recovery

### Index missing or stale for an arch whose OCI push succeeded

Re-run the **Update central index — \<arch\>** step for the affected arch
only (GitHub Actions supports re-running a single failed job; the
`build-oci` artifacts this job downloads from are retained for 1 day, so this
only works same-day). If the artifact has already expired, re-run the whole
workflow from the triggering ref/tag — `build-oci` is deterministic from
source and the registry pushes are idempotent (same tag, same digest if
nothing changed; a new digest under the same mutable tag if it did).

Do not hand-edit `static/flatpak/index/static` to patch one entry. The file
is a generated, per-repo-name keyed merge
(`.github/actions/update-flatpak-index/update-index.py`); a hand edit that
drifts from what that script would produce is exactly the drift class
`flatpak-tooling-drift-check.yml` exists to catch, and the next real publish
for that app will silently overwrite your hand edit anyway.

### One arch published, the other failed

This is the common partial state: `build-oci` runs both arches in a matrix
with `fail-fast: false`, so one arch's failure doesn't cancel the other, and
`publish` downloads/pushes/indexes each arch independently. Re-run the failed
arch's chain (its `build-oci` matrix leg, then `publish`) rather than the
whole workflow, once the underlying failure (builder error, registry
timeout) is fixed. Confirm after re-run that both
`ghcr.io/<repo-name>:latest-x86_64` and `:latest-aarch64` exist and that the
index carries both arches for this `repo-name` before considering the
release complete — a release with only one arch published is a worse outcome
than a visibly-failed run, because nothing marks it incomplete.

### `release-bundles` ran before `publish` fully succeeded

`release-bundles` only `needs: publish`, so it does not start until the
`publish` job as a whole reports success — but "success" there is per-step
`if:` gating on `inputs.attach-bundles` and `inputs.archs`, not a guarantee
every arch's index update landed (see above). If a release has bundles
attached but the index lookup above shows a missing or stale arch, treat the
GitHub release as cosmetically complete but the actual distribution
(registry + index) as still partial. Fix the registry/index state first;
the attached bundles don't need to be touched.

### Full re-run after a failure midway

Safe to do once the cause is fixed. `build-oci` is a fresh build from
source. Registry pushes overwrite the same mutable tags. Index updates are
keyed per `repo-name` and retried against the current tip of `tuna-os/docs`
on every push rejection (see `publish-flatpak-index/action.yml`), so a
re-run correctly merges on top of whatever the partial run already
committed rather than duplicating or reverting it.

## What this runbook does not cover

- Recovering from a bad build that was fully, successfully published (wrong
  app behavior, not a pipeline failure) — that is a normal revert-and-retag
  on the source repo, not a pipeline recovery.
- `FLATPAK_INDEX_TOKEN` rotation or scope — tracked separately
  (`tuna-os/.github` sec-check issues on this workflow).
- The index-tooling-drift problem (per-repo copies of `update-index.py`
  diverging from the canonical action) — see `AGENTS.md` and the open
  `[architect]` issues against `flatpak-tooling-drift-check.yml`.
