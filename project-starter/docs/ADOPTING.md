# Adopting TunaOS project patterns

## Baseline

Use a Justfile as the public local interface. `just check` must run the same fast checks that CI runs. Keep `e2e`, releases, and screenshot capture explicit or scheduled when they require privileged hardware, long execution, or secrets.

Enable the CI template only after replacing the checkout action version with the organisation’s current pinned policy and installing the project's tools. Configure branch protection to require **only** `CI / required-checks`; update its `needs` list whenever a new required job is added.

## Dependency updates

The organisation baseline automerges Renovate updates after branch protection passes. The tuned OS configuration adds custom managers for image digests and pinned workflow SHAs. Copy those custom managers only when those file formats exist. For an upstream that moves several times a day, use `minimumReleaseAge` to coalesce updates.

## Flatpak remote

The central remote pattern in `tuna-os/docs` is intentionally two-stage:

1. Build each manifest in a known Flatpak builder environment and export OCI.
2. Publish the OCI and update the central static index only after a successful build.
3. Deploy the site when `static/flatpak/**` changes.
4. Run a remote sanity check that consumes the generated `.flatpakrepo`.

Do not grant cross-repository credentials to pull-request runs. Put index mutation behind trusted events and use a dedicated, minimally scoped token.

## Documentation evidence

TunaOS captures installer/desktop screens from QEMU, uploads artifacts even on failure, validates that capture meaningfully succeeded, and then a docs-side workflow imports the newest successful artifacts and regenerates the guide. This avoids hand-maintained product tours going stale.

The reusable rule is: **test the product, retain the evidence, publish only validated evidence.**

## Release and operational guardrails

- Serialize semantic releases on the protected default branch; queue rather than cancel releases.
- Use concurrency cancellation for superseded CI, but not for releases or remote mutations.
- Retain logs and artifacts on failure. Give each long-running stage its own timeout.
- For fork PRs, never run privileged QEMU/KVM jobs or expose secrets. Guard with a same-repository condition.
- Prefer containerized development/test environments where host toolchain drift is costly.
- Commit generated assets only when changed and mark generated-doc commits to avoid recursive CI where appropriate.
