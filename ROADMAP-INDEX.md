# Org-wide ROADMAP inventory

**Last full verification**: 2026-09-02 · **Last row-level correction**: 2026-09-30 (spindle, blueshell, hive — see Coverage section) · **Source**: `gh api repos/tuna-os/<repo>/contents/ROADMAP.md?ref=<default_branch>` against every active (non-archived) repository returned by `gh repo list tuna-os --limit 200`, which was **40** repositories as of the last full pass.

tunaos#1295 and tunaos#1361 both found the same problem from different
angles: nobody — human or agent — could see at a glance which repos in the
org actually have a per-repo roadmap, so the canonical `tunaos/ROADMAP.md`
Community section kept drifting out of sync with reality (most recently:
claiming 9/42 when the real count was 15/37). This file is the
single-source-of-truth inventory that section should be checked against.

**Scope note**: `ubuntu` and `letters` are excluded — both archived
2026-08-12, confirmed via the GitHub API (`archived: true`). Archived repos
take no further planning by definition.

**Scope correction (2026-09-02)**: every table below this line through
2026-08-30 reported a denominator of 37. The real active count was larger:
`spindle`, `blueshell` and `hive` are active, non-archived `tuna-os`
repositories that had no row at all — they were not the `❌`, they were
absent. `spindle` in particular was created 2026-08-26, four days before the
last verification pass, and is now the highest-velocity repository in the org
(266 commits and 227 merged PRs in its first seven days). The denominator is a
scope problem, not a coverage problem: a table that only re-checks the repos it
already lists cannot notice a repository being created. See
`tuna-os/.github#52`.

## Coverage: 38 / 40 active repos (partial refresh)

Roadmap coverage grew from 16/37 on August 14 to 36/37 on August 30 against the
scope known at the time; re-measured against the full active set on September 2
it was 36 / 40. This pass corrects three rows the September 2 snapshot had
wrong at the time it was taken, without re-running the full org sweep: `spindle`
merged a ROADMAP.md via
[#310](https://github.com/tuna-os/spindle/pull/310) on 2026-09-03, `blueshell`
has one on its actual default branch `ptyxis-port`, and `hive` has one on its
actual default branch `v4`. The denominator and the remaining `❌` count are
carried forward from the September 2 pass and are **not** re-verified here —
run the regeneration script below against `gh repo list` to confirm both
before the next quarterly refresh. The one repository this pass can still
confirm as gapped:

- `kde-build-meta` — documented as superseded by `tromso`; its open retirement
  tracker (`tuna-os/kde-build-meta#19`) is the appropriate lifecycle decision
  instead of creating a roadmap for inactive work.

| Repo | Default branch | ROADMAP.md? |
|---|---|---|
| Tavern | main | ✅ |
| bluefin-cli | main | ✅ |
| blueshell | ptyxis-port | ✅ |
| bootc-installer | dev | ✅ (tuna-os/bootc-installer#14, merged 08-14) |
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
| .github | main | ✅ |
| bootc-installer-asahi | main | ✅ |
| branding | main | ✅ |
| bst-ci | main | ✅ |
| changelog-action | master | ✅ |
| debian-copr | main | ✅ |
| finupdate | main | ✅ |
| fisherman | dev | ✅ |
| flatpak-index | main | ✅ |
| hive | v4 | ✅ |
| homebrew-tap | main | ✅ |
| kde-build-meta | master | ❌ |
| mandelbrot | main | ✅ |
| mariner | master | ✅ |
| remora | main | ✅ |
| scoop-bucket | main | ✅ |
| spindle | main | ✅ (tuna-os/spindle#310, merged 09-03) |
| suite-common | main | ✅ |
| suite-common-rust | main | ✅ |
| tuna-installer-cosmic | main | ✅ |
| tuna-installer-kde | main | ✅ |
| tuna-installer-niri | main | ✅ |
| tuna-installer-xfce | main | ✅ |

## A note on "ROADMAP.md exists" vs. reachable

Presence alone isn't enough — `tuna-os/bootc-installer` had a `ROADMAP.md`
for two days that this exact inventory method would have missed, because it
was merged to `main` while the repo's actual default branch is `dev` (82
commits ahead). This table checks `ref=<default_branch>` explicitly, not a
hardcoded `main`, specifically to avoid repeating that miss — several repos
above (`bootc-installer`, `fisherman`, `changelog-action`, `kde-build-meta`,
`mariner`, `blueshell`, `hive`) don't default to `main`.

## A note on "every repo is listed" vs. every repo

There is a second failure mode above the first, and the September 2 pass hit
it: a row can be wrong, but a *missing row* is silent. Three active repos were
outside this table for as long as they had existed, so nothing in the inventory
— not the count, not the `❌` list, not the `tunaos/ROADMAP.md` Community
section that checks against it — could report them. Re-running the block below
starts from `gh repo list`, not from the rows already here, precisely so that
repository creation is picked up rather than only roadmap absence. Refresh the
scope, not just the answers.

## Regenerating this table

This is a manual, point-in-time snapshot, not yet an automated one. Until the
automation tracked by `tuna-os/tunaos#1295` lands, refresh it at each quarter
boundary and after any roadmap or repository lifecycle campaign:

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
- tuna-os/.github#52 — scope gap: `spindle`, `blueshell` and `hive` absent from
  the table entirely (37 → 40 denominator correction, 2026-09-02)
- tunaos/ROADMAP.md Community section — should track this table's count
