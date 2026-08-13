#!/usr/bin/env python3
"""Pick actionable work off the TunaOS hive's public ready-work queue.

The hive exposes its contribute surface unauthenticated: every route under
`/api/contribute` is a public path (see hive `v2/pkg/dashboard/server.go`,
`isPublicPath`). That means a contributor can read the queue, the fleet and
the triage ladder without registering a relay and without donating a GitHub
or inference credential.

This script does the mechanical part of picking work — fetch, deconflict,
rank — so the agent that runs afterwards spends its judgement on the fix
rather than on JSON wrangling.

Usage:
    hive_pick.py [--hub URL] [--limit N] [--json] [--include-soft]

Exit codes:
    0  at least one candidate found
    3  queue reachable but nothing admissible survived filtering
    4  hub unreachable / bad response
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request

DEFAULT_HUB = "https://hive.tunaos.org"
TIMEOUT = 30

# Repos this contributor is scoped to. The queue also serves issues on repos
# outside the scope (archived ones such as tuna-os/letters still appear), and
# claiming those wastes a cycle — the push would be rejected.
SCOPED_REPOS = {
    "iso-builder", "tunaos", "tunaos-packages", "bootc-installer",
    "tuna-installer-xfce", "tuna-installer-niri", "tuna-installer-kde",
    "docs", "mandelbrot", "tuna-installer-cosmic", "tacklebox", "corral",
    "homebrew-tap", "bootc-installer-asahi", "wootc", "remora", "tromso",
    "bootc-migrate", "finupdate", "gtk-office-suite", "suite-common",
    "xfce-linux", "bst-ci", "bluefin-cli", "protota", "flatpak-index",
    "fisherman", "dualcut", "debian-copr", "scoop-bucket", "tavern",
    "kde-build-meta", "changelog-action", "branding", "suite-common-rust",
    "mariner", ".github",
}

# Labels that mark an issue as code work an agent can actually finish and
# defend in review.
CODE_LABELS = {
    "bug", "security", "ci", "documentation", "good first issue",
    "quality", "enhancement", "infrastructure", "testing",
}

# Labels that mark work needing a human: posting to forums, courting adopters,
# setting product direction. An agent opening a PR against these is noise.
HUMAN_LABELS = {"outreach", "community", "roadmap", "strategic", "hive/advisory"}

# Recurring bot-authored status reports. They are open issues on the queue but
# they are artifacts, not tasks.
REPORT_MARKERS = (
    "weekly boot report", "hive advisory report", "dependency dashboard",
    "weekly desktop screenshots", "nightly report",
)


# The hub sits behind an edge that rejects the default `Python-urllib/3.x`
# User-Agent with a 403 — which reads exactly like an egress-policy denial and
# is not one. Always send a real UA.
USER_AGENT = "tunaos-hive-pick/1.0 (+https://github.com/tuna-os/.github)"


def fetch(hub: str, path: str) -> dict:
    url = f"{hub.rstrip('/')}/api/contribute/{path}"
    req = urllib.request.Request(
        url, headers={"Accept": "application/json", "User-Agent": USER_AGENT}
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return json.loads(r.read().decode("utf-8"))


def repo_key(full_name: str) -> str:
    """`tuna-os/TunaOS` -> `tunaos`. The queue and GitHub disagree on case."""
    return full_name.split("/")[-1].lower()


def issue_key(repo: str, number: int) -> str:
    return f"{repo_key(repo)}#{number}"


def in_flight(fleet: dict) -> set[str]:
    """Issues a connected clanker is working on right now.

    Without a registered relay we hold no lease, so this is the only
    deconfliction signal available. It is a snapshot, not a lock — a race is
    still possible, which is why the caller re-checks for an open PR on
    GitHub before starting work.
    """
    keys = set()
    for c in fleet.get("clankers") or []:
        task = c.get("current_task")
        if task and task.get("repo") and task.get("number") is not None:
            keys.add(issue_key(task["repo"], task["number"]))
    for w in fleet.get("work") or []:
        if w.get("repo") and w.get("number") is not None:
            keys.add(issue_key(w["repo"], w["number"]))
    return keys


def ready_set(triage: dict) -> set[str]:
    """Issues the hive places at `ready` on the lifecycle ladder.

    Anything at `implementing` or `reviewing` already has an agent or an open
    PR behind it.
    """
    keys = set()
    for g in triage.get("groups") or []:
        if g.get("level") != "ready":
            continue
        for i in g.get("issues") or []:
            keys.add(issue_key(i["repo"], i["number"]))
    return keys


def classify(item: dict) -> tuple[bool, str]:
    """Return (is_code_work, reason-if-not)."""
    labels = {l.lower() for l in (item.get("labels") or [])}
    title = (item.get("title") or "").lower()

    if repo_key(item["repo"]) not in SCOPED_REPOS:
        return False, "out of contributor repo scope"
    if any(m in title for m in REPORT_MARKERS):
        return False, "recurring bot status report, not a task"
    if labels & CODE_LABELS:
        return True, ""
    if labels & HUMAN_LABELS:
        return False, "needs a human (outreach/roadmap judgement)"
    # Unlabelled issues are common and often real work; the bracket-prefix
    # convention (`[quality]`, `[architect]`, `[guide]`) is the hive's own
    # agent-authored marker and is a reliable signal.
    if title.startswith(("[quality]", "[guide]", "[ci-maintainer]", "[bug]", "[sec-check]")):
        return True, ""
    if title.startswith("[architect]") or title.startswith("[strategist]"):
        return False, "architecture/strategy proposal — wants a design decision first"
    return False, "no actionable label or recognised prefix"


def rank(item: dict) -> tuple:
    """Lower sorts first. Prefer small, verifiable, high-signal work."""
    labels = {l.lower() for l in (item.get("labels") or [])}
    title = (item.get("title") or "").lower()
    if "good first issue" in labels:
        band = 0
    elif "security" in labels or title.startswith("[sec-check]"):
        band = 1
    elif "bug" in labels or title.startswith("[bug]"):
        band = 1
    elif title.startswith("[quality]"):
        band = 2
    elif "ci" in labels:
        band = 3
    elif "documentation" in labels or title.startswith("[guide]"):
        band = 4
    else:
        band = 5
    return (band, repo_key(item["repo"]), item["number"])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--hub", default=DEFAULT_HUB)
    ap.add_argument("--limit", type=int, default=10)
    ap.add_argument("--json", action="store_true", help="emit JSON not text")
    ap.add_argument("--include-soft", action="store_true",
                    help="also list what was filtered out, with reasons")
    args = ap.parse_args()

    try:
        queue = fetch(args.hub, "queue").get("queue") or []
        fleet = fetch(args.hub, "fleet")
        triage = fetch(args.hub, "triage")
    except (urllib.error.URLError, ValueError, KeyError) as e:
        print(f"hub unreachable or bad response: {e}", file=sys.stderr)
        return 4

    busy = in_flight(fleet)
    ready = ready_set(triage)

    picks, rejected = [], []
    for item in queue:
        key = issue_key(item["repo"], item["number"])
        ok, why = classify(item)
        if not ok:
            rejected.append({**item, "reason": why})
            continue
        if key in busy:
            rejected.append({**item, "reason": "a clanker is working it now"})
            continue
        # `ready` is authoritative when the ladder knows the issue at all.
        if ready and key not in ready:
            rejected.append({**item, "reason": "not at 'ready' on the triage ladder"})
            continue
        picks.append(item)

    picks.sort(key=rank)
    picks = picks[: args.limit]

    if args.json:
        print(json.dumps({"picks": picks, "rejected": rejected if args.include_soft else [],
                          "counts": {"queue": len(queue), "picks": len(picks),
                                     "rejected": len(rejected), "in_flight": len(busy)}},
                         indent=2))
    else:
        print(f"queue={len(queue)}  in-flight={len(busy)}  "
              f"candidates={len(picks)}  filtered={len(rejected)}\n")
        for i, p in enumerate(picks, 1):
            labels = ",".join(p.get("labels") or []) or "-"
            print(f"{i:2}. {p['repo']}#{p['number']}  [{labels}]")
            print(f"    {p['title']}")
            print(f"    {p['url']}")
        if args.include_soft:
            print("\n--- filtered ---")
            for r in rejected[:40]:
                print(f"  {r['repo']}#{r['number']}: {r['reason']}")

    return 0 if picks else 3


if __name__ == "__main__":
    sys.exit(main())
