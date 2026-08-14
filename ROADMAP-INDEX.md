# Org-wide ROADMAP inventory

**Last verified**: 2026-08-13 · **Source**: `gh api repos/tuna-os/<repo>/contents/ROADMAP.md?ref=<default_branch>` against every active (non-archived) repo in the `tuna-os` org.

tunaos#1295 and tunaos#1361 both found the same problem from different
angles: nobody — human or agent — could see at a glance which repos in the
org actually have a per-repo roadmap, so the canonical `tunaos/ROADMAP.md`
Community section kept drifting out of sync with reality (most recently:
claiming 9/42 when the real count was 15/37). This file is the
single-source-of-truth inventory that section should be checked against.

**Scope note**: `ubuntu` and `letters` are excluded — both archived
2026-08-12, confirmed via the GitHub API (`archived: true`). Archived repos
take no further planning by definition.

## Coverage: 16 / 37 active repos

| Repo | Default branch | ROADMAP.md? |
|---|---|---|
| Tavern | main | ✅ |
| bluefin-cli | main | ✅ |
| bootc-installer | dev | ✅ (tuna-os/bootc-installer#14, pending merge) |
| bootc-migrate | main | ✅ |
| corral | main | ✅ |
| docs | main | ✅ |
| dualcut | main | ✅ |
| gtk-office-suite | main | ✅ |
| iso-builder | main | ✅ |
| protota | main | ✅ |
| tacklebox | main | ✅ |
| tromso | main | ✅ |
| tunaOS | main | ✅ |
| tunaos-packages | main | ✅ |
| wootc | main | ✅ |
| xfce-linux | main | ✅ |
| .github | main | ❌ |
| bootc-installer-asahi | main | ❌ |
| branding | main | ❌ |
| bst-ci | main | ❌ |
| changelog-action | master | ❌ |
| debian-copr | main | ❌ |
| finupdate | main | ❌ |
| fisherman | dev | ❌ |
| flatpak-index | main | ❌ |
| homebrew-tap | main | ❌ |
| kde-build-meta | master | ❌ |
| mandelbrot | main | ❌ |
| mariner | master | ❌ |
| remora | main | ❌ |
| scoop-bucket | main | ❌ |
| suite-common | main | ❌ |
| suite-common-rust | main | ❌ |
| tuna-installer-cosmic | main | ❌ |
| tuna-installer-kde | main | ❌ |
| tuna-installer-niri | main | ❌ |
| tuna-installer-xfce | main | ❌ |

## A note on "ROADMAP.md exists" vs. reachable

Presence alone isn't enough — `tuna-os/bootc-installer` had a `ROADMAP.md`
for two days that this exact inventory method would have missed, because it
was merged to `main` while the repo's actual default branch is `dev` (82
commits ahead). This table checks `ref=<default_branch>` explicitly, not a
hardcoded `main`, specifically to avoid repeating that miss — several repos
above (`bootc-installer`, `fisherman`, `changelog-action`, `kde-build-meta`,
`mariner`) don't default to `main`.

## Regenerating this table

This is a manual, point-in-time snapshot, not yet an automated one. To
refresh it:

```bash
gh repo list tuna-os --limit 200 --json name,isArchived --jq \
  '.[] | select(.isArchived==false) | .name' | sort > /tmp/active_repos.txt
while read -r repo; do
  branch=$(gh api "repos/tuna-os/$repo" --jq '.default_branch')
  if gh api "repos/tuna-os/$repo/contents/ROADMAP.md?ref=$branch" >/dev/null 2>&1; then
    echo "$repo|$branch|yes"
  else
    echo "$repo|$branch|no"
  fi
done < /tmp/active_repos.txt
```

Note the exit-code check (`>/dev/null 2>&1; then`) rather than capturing
`gh api`'s stdout with a `--jq` filter and checking string emptiness — on a
404, `gh api` prints the raw JSON error body to stdout *past* a `--jq`
filter, which produces false "has a roadmap" positives if you test the
captured string instead of the command's exit status.

**Proposed next step** (not done in this pass): wire the block above into a
scheduled GitHub Actions workflow in this repo (`bst-ci`-style) that
re-generates this table and opens a PR on drift, so it can't go stale the
way `tunaos/ROADMAP.md`'s Community section did. Deliberately not
implementing that blind in this pass — a scheduled workflow needs a real
CI run to validate, not just local reasoning about the script.

## Related

- tunaos#1295 — original coverage-gap finding (5/38 at filing)
- tunaos#1361 — inventory-drift finding + bootc-installer stranded-branch bug
- tunaos/ROADMAP.md Community section — should track this table's count
