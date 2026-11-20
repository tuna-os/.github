#!/usr/bin/env python3
"""Count cargo-deny ignore entries without a reason and a review date.

Usage: deny_review_dates.py [deny.toml ...]   (default: ./deny.toml)

An entry passes when it is a table with a `reason` that contains an ISO date
(the house form is "...; review by 2027-01-01"). A bare string entry, or a
table without a reason or date, is counted. Entries whose review date has
passed are reported as warnings but are not counted, so a date going by
does not turn main red overnight -- the warning is the reminder.

Prints one line per finding, then the total as the last line, which is the
contract of a count-ratchet `command` metric.
"""

import datetime
import re
import sys
import tomllib

DATE = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")


def findings(path):
    with open(path, "rb") as fh:
        data = tomllib.load(fh)
    entries = (data.get("advisories") or {}).get("ignore") or []
    today = datetime.date.today()
    bad, expired = [], []
    for entry in entries:
        if isinstance(entry, str):
            bad.append(f"{path}: {entry}: bare id, needs {{ id, reason = \"...; review by YYYY-MM-DD\" }}")
            continue
        ident = entry.get("id") or entry.get("crate") or "?"
        reason = entry.get("reason") or ""
        m = DATE.search(reason)
        if not reason:
            bad.append(f"{path}: {ident}: no reason")
        elif not m:
            bad.append(f"{path}: {ident}: reason has no review date (add '; review by YYYY-MM-DD')")
        else:
            try:
                when = datetime.date.fromisoformat(m.group(1))
            except ValueError:
                bad.append(f"{path}: {ident}: review date {m.group(1)} is not a real date")
                continue
            if when < today:
                expired.append(f"{path}: {ident}: review date {when} has passed")
    return bad, expired


def main(argv):
    paths = argv or ["deny.toml"]
    total = 0
    for path in paths:
        bad, expired = findings(path)
        for line in bad:
            print(line)
        for line in expired:
            print(f"::warning::{line}")
        total += len(bad)
    print(total)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
