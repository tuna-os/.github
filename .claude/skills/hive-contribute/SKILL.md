---
name: hive-contribute
description: Pick one actionable issue off the TunaOS hive's public ready-work queue and take it to a reviewed PR. Use when asked to contribute to TunaOS, work the hive backlog, pick up hive work, or when running as a scheduled contribution job. Requires no hive registration or donated credentials.
---

# Contributing to the TunaOS hive without a relay

## Why this exists

The documented contribution path at <https://hive.tunaos.org/contribute> is
ClankeR, a relay: you register a machine, donate a long-lived GitHub PAT and
your CLI's inference credentials, and the hub pushes tasks to an agent running
on your box over a WebSocket.

That path needs three things a sandboxed or ephemeral agent session does not
have: an interactive browser for `gh auth login --web`, a donated personal
credential, and a host that stays up long enough to hold a task lease.

It turns out none of that is required to do the actual work. Every route under
`/api/contribute` is an unconditional public path — see `isPublicPath` in the
hive's `v2/pkg/dashboard/server.go`:

```go
case strings.HasPrefix(path, "/api/contribute"):
    return true
```

So the backlog, the fleet's in-flight work, and the triage ladder are all
readable anonymously. This skill reads them, picks one issue, and does the
work with whatever GitHub credential the session already legitimately holds.

**What you give up by not registering:** you hold no task lease, so there is
no hard deconfliction, and completed work earns no leaderboard attribution.
The soft deconfliction below is a mitigation, not a substitute — treat a race
as possible on every run.

## Endpoints used

| Endpoint | Gives you |
|---|---|
| `GET /api/contribute/queue` | admissible issues, cooldown + operator holds already applied server-side |
| `GET /api/contribute/fleet` | connected clankers and each one's `current_task` |
| `GET /api/contribute/triage` | lifecycle ladder: `triaging` → `ready` → `implementing` → `reviewing` → `closed` |
| `GET /api/contribute/status` | hub health, actionable count |

The hub's edge rejects the default `Python-urllib/3.x` User-Agent with a 403
that looks exactly like an egress-policy denial and is not one. Send a real UA.

## Procedure

### 1. Pick

```bash
python3 .claude/skills/hive-contribute/hive_pick.py --limit 10
# --json for machine output, --include-soft to see what was filtered and why
```

The script fetches all three endpoints, then drops: issues outside the
contributor's repo scope, recurring bot status reports, work a clanker is
holding right now, anything past `ready` on the ladder, and outreach/roadmap
items that need human judgement rather than a patch. What survives is ranked
good-first-issue → security/bug → quality → CI → docs.

Exit `3` means the queue was reachable but nothing survived — that is a normal
quiet result, not a failure. Say so and stop.

### 2. Re-check before starting

The fleet snapshot is not a lock. Before touching code, confirm on GitHub that
the issue is still open, unassigned, and has no open PR already referencing it.
If it does, drop it and take the next candidate.

### 3. Do the work

Read the issue fully, including comments — hive issues are agent-authored and
the comments frequently correct the body. **Verify the claim before
implementing it.** These reports are often right about the symptom and wrong
about the fix; two real examples:

- `gtk-office-suite#211` was already fixed on main and merely left open.
- `gtk-office-suite#172` proposed a guard that contradicted the expected
  behaviour asserted three lines further down in the same issue.

If the issue's suggested fix is wrong, implement the correct one and say
plainly in the PR why you deviated.

### 4. Verify locally

Build and test before pushing. Follow the target repo's `CLAUDE.md` for its
commands. Missing system dependencies are usually installable (`apt-get install
libgtk-4-dev` and friends) — do that rather than pushing unverified.

Distinguish pre-existing failures from ones you caused: check whether the
failing target even depends on what you touched, and say which is which in the
PR. Never weaken a test to make it pass.

### 5. Open the PR

One issue per run. Reference the issue with `Fixes #N`. State what you
verified, what you did not, and any pre-existing breakage you found on the way.
Then stop — do not batch a second issue into the same run.

## Where this runs

The hive half of this skill needs no credentials anywhere. The GitHub half does,
and that is what varies by session type.

**Interactive cloud session — works.** The session holds a scoped GitHub grant
(exposed as `mcp__github__*` tools) covering the org's repos, which is enough to
branch, push, and open a PR. This is the configuration that produced
`tuna-os/gtk-office-suite#217`.

**Scheduled / trigger-fired session — read-only, cannot ship.** Verified by
firing a routine and having it report its own tooling:

- no `mcp__*` tools of any kind are injected, so there is no `mcp__github__*`
  and no `add_repo` either
- `GH_TOKEN` and `GITHUB_TOKEN` are set to the literal placeholder
  `proxy-injected`; `gh auth status` rejects it
- any authenticated call returns `GitHub access to this repository is not
  enabled for this session. Use add_repo to request access` — and the tool it
  names is not available to ask with
- `gh repo fork` is separately refused by the permission classifier as an
  unattended state-changing action
- anonymous reads (`git clone`, `git ls-remote`, WebFetch on issue pages) all
  succeed, so the picker and the research half work fine

So a routine created from inside a session **inherits none of that session's
repo access**. Before scheduling this skill, confirm the fired session can
actually reach GitHub — otherwise every run does the analysis and the
implementation and then has nowhere to put them. Create the routine from the
claude.ai routines UI, or from a surface that attaches repo access to fired
sessions.

## Guardrails

- **Scope.** Only repos in `SCOPED_REPOS` in the picker. The queue serves
  issues on archived and out-of-scope repos (`tuna-os/letters`); a push there
  fails after the work is already done.
- **One issue per run**, so a bad run costs one PR and not twelve.
- **No silent scope growth.** Fix the issue, not everything nearby. File a
  follow-up issue instead of widening the diff.
- **Report honestly.** A run that finds nothing, or that hits a blocker, should
  say so. A quiet accurate run beats a PR that had to invent work to exist.
