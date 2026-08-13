# update-flatpak-index

Canonical, single-source copy of `update-index.py` (tuna-os/tunaos#1183: the
script was byte-copied — identical git blob `127aed10...` — across 8 repos,
each independently drifting).

## Usage

Replace a repo's local `python3 .github/scripts/update-index.py ...` call
with:

```yaml
- uses: tuna-os/.github/.github/actions/update-flatpak-index@main
  with:
    oci-dir: oci/mandelbrot-oci-x86_64
    index-file: index-repo/static/flatpak/index/static
    repo-name: tuna-os/mandelbrot
    tags: latest
```

`registry` defaults to `ghcr.io`; `index-file` defaults to `index/static`.
For multi-arch publishes, call the action once per architecture (matching
the existing per-repo loop pattern) — `update-index.py` only ever replaces
the entry for the architecture it was given, leaving other arches in the
index untouched.

## Migration status

This action was added as the first step of the tunaos#1183 consolidation
(recommendation #1: host the script once, consume via composite action). It
has **not yet been adopted** by any of the 8 duplicate-carrying repos —
`.github/scripts/update-index.py` in tuna-installer-{cosmic,kde,niri,xfce},
bootc-installer, dualcut, mandelbrot, and gtk-office-suite still carry their
own copy. Migrating each caller (swapping the `python3 .github/scripts/...`
step for this action, then deleting the repo's local copy) is a follow-up PR
per repo — each one touches a live publish pipeline this project can't test
without a real OCI build, so it's intentionally out of scope for this PR.

Recommendation #3 from tunaos#1183 (an interim drift-guard that fails when a
repo's committed copy diverges from canonical) is implemented separately in
[`.github/workflows/flatpak-tooling-drift-check.yml`](../../workflows/flatpak-tooling-drift-check.yml).

Recommendation #2 (a reusable `publish-flatpak.yml` workflow) is a larger
follow-up: it needs to parameterize the full build→publish→index pipeline
across 8 repos' Containerfiles/manifests, which is out of scope here.
