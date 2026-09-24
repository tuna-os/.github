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

Set `require-appstream: "true"` to fail the publish instead of only warning
when an image carries no `org.freedesktop.appstream.*` labels (see below).

## Keep this in lockstep with tuna-os/flatpak-index

`update-index.py` here and
[`tuna-os/flatpak-index`'s `scripts/update-index.py`](https://github.com/tuna-os/flatpak-index/blob/main/scripts/update-index.py)
are two copies of the same publisher logic that this repo's own drift-check
does not compare against each other — it only compares the 8 legacy vendored
copies against *this* file. A fix landed in flatpak-index (`--require-appstream`,
the `filter_labels`/`build_image_entry`/`merge_entry` split, and
result-sorting in `merge_entry`) without being ported here until this file
was brought back in sync; check `tests/test_update_index.py` there against
`test-update-index.py` here after editing either copy.

Run the tests here with `python3 test-update-index.py`.

## Migration status

This action was added as the first step of the tunaos#1183 consolidation
(recommendation #1: host the script once, consume via composite action).
[`publish-flatpak.yml`](../../workflows/publish-flatpak.yml) (recommendation
#2, a reusable build→GHCR→index pipeline) now calls this action indirectly
through [`publish-flatpak-index`](../publish-flatpak-index), so any caller
on that reusable workflow already gets this file's logic — the note that
recommendation #2 was future work is stale.

The 8 duplicate-carrying repos this action's drift-check still tracks by
hash (`.github/scripts/update-index.py` in
tuna-installer-{cosmic,kde,niri,xfce}, bootc-installer, dualcut, mandelbrot,
and gtk-office-suite) may or may not have migrated onto `publish-flatpak.yml`
since; that migration status wasn't re-verified as part of this update. Each
migration is still a follow-up PR per repo, since it touches a live publish
pipeline this project can't test without a real OCI build.

Recommendation #3 from tunaos#1183 (an interim drift-guard that fails when a
repo's committed copy diverges from canonical) is implemented separately in
[`.github/workflows/flatpak-tooling-drift-check.yml`](../../workflows/flatpak-tooling-drift-check.yml).
That guard's "canonical" reference is this action's `update-index.py`, so it
catches the 8 legacy repos drifting from *this* file, but nothing currently
catches this file drifting from flatpak-index's copy — see "Keep this in
lockstep" above.

