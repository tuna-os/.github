#!/usr/bin/env python3
"""Fail if a repo's renovate.json would automerge a major update.

Org policy (tuna-os/.github#12): minor/patch/pin/pinDigest/digest updates may
automerge once CI is green. major updates always need human review before
merge.

Minor was moved out of the blocked set deliberately, not by erosion: it is the
bulk of the fleet's dependency traffic, and holding it for review produced a
review queue nobody read, which is its own failure mode. Major stays blocked
because that is the class both incidents below were actually about.

This is deliberately conservative, not a full Renovate rule-matching engine:
it ignores matchDatasources/matchPackageNames/matchManagers scoping and
treats any packageRule whose matchUpdateTypes includes (or omits, meaning
"all") "major" or "minor" as applying org-wide. That can flag a rule that,
in practice, only ever matches one specific low-risk package (a false
positive a human then has to look at) -- but it can never silently miss a
real gate bypass by being too narrow. For a security gate, erring toward
"flag more, let a human confirm" is the correct default; erring the other
way is exactly the class of incident this script exists to catch (see
tuna-os/tunaOS#1612, tuna-os/tunaOS#1636).

Usage:
    check-renovate-automerge-policy.py [path/to/renovate.json]

Exit codes:
    0  compliant (no rule automerges major)
    1  violation found (or the file could not be parsed)
"""

from __future__ import annotations

import json
import sys

RISKY_TYPES = {"major"}

# Renovate matcher keys that narrow a packageRule to a subset of packages,
# beyond matchUpdateTypes. A rule that uses any of these can only ever
# clear a violation *for the packages it matches* -- not universally -- so
# it must never be allowed to cancel a broader violation an earlier rule
# introduced. (Found by testing this script against protota's real,
# pre-fix renovate.json: a narrow fedora-image-only rule that set
# automerge: false for "major" was wrongly letting an earlier, unscoped
# "automerge everything" rule's major-update violation disappear. A
# narrow override is not evidence the broad bypass stopped applying to
# every other package.)
SCOPING_KEYS = {
    "matchPackageNames",
    "matchPackagePatterns",
    "matchPackagePrefixes",
    "matchDepNames",
    "matchDepPatterns",
    "matchDepTypes",
    "matchDatasources",
    "matchManagers",
    "matchFileNames",
    "matchSourceUrls",
    "matchCurrentVersion",
    "matchCurrentValue",
    "matchBaseBranches",
    "matchLanguages",
    "matchCategories",
}


def check(config: dict) -> list[str]:
    """Return a list of human-readable violation descriptions, empty if none."""
    violations = {}  # risky type -> description of the rule that caused it

    # Track the running automerge state for each risky type as if a real
    # update of that type were being resolved: start from the top-level
    # default, then apply each *unscoped* packageRule in order (later rules
    # win), exactly like Renovate itself layers config. Scoped rules are
    # judged independently instead of participating in this chain -- see
    # SCOPING_KEYS above for why.
    unscoped_state = {t: bool(config.get("automerge", False)) for t in RISKY_TYPES}
    unscoped_source = {t: "top-level automerge" for t in RISKY_TYPES}

    for i, rule in enumerate(config.get("packageRules", [])):
        if "automerge" not in rule:
            continue
        match_types = rule.get("matchUpdateTypes")
        # No matchUpdateTypes at all means the rule applies to every update
        # type, major included.
        applies_to = RISKY_TYPES if match_types is None else RISKY_TYPES & set(match_types)
        if not applies_to:
            continue

        is_scoped = bool(SCOPING_KEYS & rule.keys())
        label = f"packageRules[{i}]" + (
            f" ({rule['description']!r})" if rule.get("description") else ""
        )

        if is_scoped:
            # Only ever adds a (narrower) violation of its own; never
            # clears a broader one already recorded from the unscoped chain.
            if rule["automerge"]:
                violations.setdefault(
                    frozenset(applies_to), f"{label} (package-scoped)"
                )
            continue

        for t in applies_to:
            unscoped_state[t] = bool(rule["automerge"])
            unscoped_source[t] = label

    for t in sorted(RISKY_TYPES):
        if unscoped_state[t]:
            violations[frozenset([t])] = unscoped_source[t]

    out = []
    for types, source in violations.items():
        for t in sorted(types):
            out.append(
                f"'{t}' updates would automerge, set by {source} "
                f"-- org policy (tuna-os/.github#12) requires human review "
                f"for major updates."
            )
    return out


def main() -> int:
    path = sys.argv[1] if len(sys.argv) > 1 else "renovate.json"
    try:
        with open(path, encoding="utf-8") as f:
            config = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        print(f"ERROR: could not read/parse {path}: {e}", file=sys.stderr)
        return 1

    violations = check(config)
    if violations:
        print(f"FAIL: {path} violates the org automerge policy:", file=sys.stderr)
        for v in violations:
            print(f"  - {v}", file=sys.stderr)
        return 1

    print(f"OK: {path} does not automerge major updates.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
