#!/usr/bin/env python3
"""count-ratchet: hold counted metrics at a budget that only goes down.

Two modes share one set of rules:

  ratchet.py check   [--config .ratchet.toml] [--base-ref main] [--labels JSON]
  ratchet.py number  --name ste --count N --budget-file .ste-budget [...]
  ratchet.py tighten [--config .ratchet.toml]   # write budget = count locally

The rules, for every metric:

  count > budget          fail: the change added what the metric counts.
  count < budget          fail: slack. The error names the exact new budget.
  budget > base budget    fail on a pull request, unless it has the raise label.
  metric deleted          treated as a raise.

Standard library only (tomllib needs Python 3.11 or later).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

if sys.version_info < (3, 11):  # pragma: no cover - environment guard
    sys.exit("count-ratchet needs Python 3.11 or later (tomllib)")

import tomllib

DEFAULT_CONFIG = ".ratchet.toml"
DEFAULT_LABEL = "ratchet-raise"
# The one Rust-aware rule: everything from `#[cfg(test)] mod x {` (or
# `#[cfg(all(test, ...))]`) to the end of the file is test code. It matches the
# house layout (tests at the bottom).
RUST_TEST_MOD = re.compile(
    # Each repetition consumes exactly one line (blank, attribute or comment),
    # and is possessive, so a long run of commented-out code cannot backtrack
    # exponentially.
    r"#\[cfg\((?:test|all\([^)\n]*\btest\b[^)\n]*\))\)\][ \t]*\r?\n"
    r"(?:[ \t]*+(?:#\[[^\n]*|//[^\n]*)?\r?\n)*+"
    r"[ \t]*(?:pub(?:\([^)\n]*\))?[ \t]+)?mod[ \t]+(\w+)[ \t]*([;{])"
)
METRIC_KEYS = {
    "description", "pattern", "command", "include", "exclude",
    "exclude-rust-tests", "budget",
}
DEFAULT_KEYS = {"include", "exclude", "exclude-rust-tests"}


class ConfigError(Exception):
    pass


# --------------------------------------------------------------------------
# Globs


def glob_to_regex(glob: str) -> re.Pattern[str]:
    """Translate a path glob to a regex.

    `**` matches any number of directories (including none), `*` and `?` stay
    inside one path segment, and `[...]` is a character class. A glob without
    a slash matches the file name at any depth, as in .gitignore.
    """
    if "/" not in glob:
        glob = "**/" + glob
    out = []
    i = 0
    while i < len(glob):
        c = glob[i]
        if glob.startswith("**/", i):
            out.append("(?:.*/)?")
            i += 3
        elif glob.startswith("**", i):
            out.append(".*")
            i += 2
        elif c == "*":
            out.append("[^/]*")
            i += 1
        elif c == "?":
            out.append("[^/]")
            i += 1
        elif c == "[":
            j = glob.find("]", i + 1)
            if j == -1:
                out.append(re.escape(c))
                i += 1
            else:
                out.append("[" + glob[i + 1:j].replace("\\", "\\\\") + "]")
                i = j + 1
        else:
            out.append(re.escape(c))
            i += 1
    return re.compile("".join(out) + r"\Z")


def compile_globs(globs, key, name):
    if isinstance(globs, str):
        globs = [globs]
    if not isinstance(globs, list) or not all(isinstance(g, str) for g in globs):
        raise ConfigError(f"metric {name!r}: {key} must be a list of glob strings")
    return [glob_to_regex(g) for g in globs]


# --------------------------------------------------------------------------
# Configuration


@dataclass
class Metric:
    name: str
    budget: int
    description: str = ""
    pattern: re.Pattern[str] | None = None
    command: str | None = None
    include: list = field(default_factory=list)
    exclude: list = field(default_factory=list)
    exclude_rust_tests: bool = False


def parse_config(text: str, source: str = DEFAULT_CONFIG) -> dict[str, Metric]:
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"{source}: {exc}") from exc
    defaults = data.get("defaults", {})
    if not isinstance(defaults, dict) or set(defaults) - DEFAULT_KEYS:
        raise ConfigError(f"{source}: [defaults] may only set {', '.join(sorted(DEFAULT_KEYS))}")
    metrics = data.get("metrics")
    if not isinstance(metrics, dict) or not metrics:
        raise ConfigError(f"{source}: no [metrics.<name>] tables")
    unknown_top = set(data) - {"defaults", "metrics"}
    if unknown_top:
        raise ConfigError(f"{source}: unknown top-level key(s): {', '.join(sorted(unknown_top))}")
    out = {}
    for name, raw in metrics.items():
        if not isinstance(raw, dict):
            raise ConfigError(f"{source}: metrics.{name} must be a table")
        merged = {**defaults, **raw}
        unknown = set(merged) - METRIC_KEYS
        if unknown:
            raise ConfigError(f"{source}: metric {name!r}: unknown key(s): {', '.join(sorted(unknown))}")
        budget = merged.get("budget")
        if not isinstance(budget, int) or isinstance(budget, bool) or budget < 0:
            raise ConfigError(f"{source}: metric {name!r}: budget must be a non-negative integer")
        has_pattern = "pattern" in merged
        has_command = "command" in merged
        if has_pattern == has_command:
            raise ConfigError(f"{source}: metric {name!r}: set exactly one of pattern or command")
        m = Metric(name=name, budget=budget, description=str(merged.get("description", "")))
        if has_pattern:
            try:
                m.pattern = re.compile(merged["pattern"], re.M)
            except re.error as exc:
                raise ConfigError(f"{source}: metric {name!r}: bad pattern: {exc}") from exc
            m.include = compile_globs(merged.get("include", ["**"]), "include", name)
            m.exclude = compile_globs(merged.get("exclude", []), "exclude", name)
            m.exclude_rust_tests = bool(merged.get("exclude-rust-tests", False))
        else:
            if not isinstance(merged["command"], str):
                raise ConfigError(f"{source}: metric {name!r}: command must be a string")
            m.command = merged["command"]
        out[name] = m
    return out


def budgets_of(text: str, source: str) -> dict[str, int]:
    """Budgets only. Used for the base branch, whose config may be older."""
    data = tomllib.loads(text)
    return {
        name: raw.get("budget")
        for name, raw in data.get("metrics", {}).items()
        if isinstance(raw, dict) and isinstance(raw.get("budget"), int)
    }


# --------------------------------------------------------------------------
# Counting


def tracked_files(root: Path) -> list[str]:
    out = subprocess.run(
        ["git", "-C", str(root), "ls-files", "-z", "--cached"],
        check=True, capture_output=True,
    ).stdout.decode("utf-8", "surrogateescape")
    return sorted(p for p in out.split("\0") if p and (root / p).is_file())


def rust_test_files(root: Path, files: list[str]) -> set[str]:
    """Files declared as `#[cfg(test)] mod name;` from a non-test parent."""
    found = set()
    for rel in files:
        if not rel.endswith(".rs"):
            continue
        text = read_text(root / rel)
        if text is None:
            continue
        p = Path(rel)
        base = p.parent if p.name in ("mod.rs", "lib.rs", "main.rs") else p.with_suffix("")
        for m in RUST_TEST_MOD.finditer(text):
            if m.group(2) == ";":
                found.add((base / f"{m.group(1)}.rs").as_posix())
                found.add((base / m.group(1)).as_posix() + "/")
    return found


def read_text(path: Path) -> str | None:
    try:
        raw = path.read_bytes()
    except OSError:
        return None
    if b"\0" in raw[:8192]:
        return None  # binary
    return raw.decode("utf-8", "replace")


def strip_rust_tests(text: str) -> str:
    """Drop everything from the first inline `#[cfg(test)] mod x {` on.

    A declaration (`mod x;`) is not a body to strip; its file is excluded
    separately by rust_test_files.
    """
    for m in RUST_TEST_MOD.finditer(text):
        if m.group(2) == "{":
            return text[: m.start()]
    return text


def matches(rel: str, globs) -> bool:
    return any(g.match(rel) for g in globs)


def count_pattern(metric: Metric, root: Path, files: list[str], rust_tests: set[str]):
    per_file = {}
    for rel in files:
        if not matches(rel, metric.include) or matches(rel, metric.exclude):
            continue
        if metric.exclude_rust_tests and rel.endswith(".rs"):
            if rel in rust_tests or any(rel.startswith(d) for d in rust_tests if d.endswith("/")):
                continue
        text = read_text(root / rel)
        if text is None:
            continue
        if metric.exclude_rust_tests and rel.endswith(".rs"):
            text = strip_rust_tests(text)
        n = len(metric.pattern.findall(text))
        if n:
            per_file[rel] = n
    return sum(per_file.values()), per_file


def count_command(metric: Metric, root: Path, action_path: str):
    env = {**os.environ, "RATCHET_ACTION_PATH": action_path}
    proc = subprocess.run(
        ["bash", "-o", "pipefail", "-c", metric.command],
        cwd=root, env=env, capture_output=True, text=True,
    )
    lines = [ln.strip() for ln in proc.stdout.splitlines() if ln.strip()]
    # Everything above the count is the command's own detail (which entries,
    # which files); pass it through so a failure says what to fix.
    for ln in lines[:-1]:
        print(ln if ln.startswith("::") else f"  [{metric.name}] {ln}")
    if proc.returncode != 0 or not lines or not re.fullmatch(r"\d+", lines[-1]):
        raise ConfigError(
            f"metric {metric.name!r}: command must exit 0 and print a count as its last line; "
            f"exit {proc.returncode}, stdout tail {lines[-3:]!r}, stderr tail "
            f"{proc.stderr.strip().splitlines()[-3:]!r}"
        )
    return int(lines[-1]), {}


# --------------------------------------------------------------------------
# Verdicts


@dataclass
class Result:
    name: str
    count: int
    budget: int
    base_budget: int | None
    per_file: dict
    problems: list = field(default_factory=list)


def judge(results, base_budgets, removed, is_pr, labels, raise_label, edit_hint):
    """Attach problems to each result; return the list of failure messages."""
    failures = []
    raise_ok = raise_label in labels
    for r in results:
        if r.count > r.budget:
            r.problems.append("over")
            failures.append(
                f"{r.name}: {r.count} > budget {r.budget}. This change adds "
                f"{r.count - r.budget}; remove them rather than raise the budget."
            )
        elif r.count < r.budget:
            r.problems.append("slack")
            failures.append(
                f"{r.name}: {r.count} < budget {r.budget}. Lock in the improvement: "
                f"{edit_hint(r.name, r.count)}"
            )
        if is_pr and r.base_budget is not None and r.budget > r.base_budget:
            if raise_ok:
                r.problems.append("raised (label)")
            else:
                r.problems.append("raised")
                failures.append(
                    f"{r.name}: budget raised {r.base_budget} -> {r.budget} versus the base branch. "
                    f"Raising a budget needs the '{raise_label}' label on the pull request."
                )
    for name in removed:
        if is_pr and not raise_ok:
            failures.append(
                f"{name}: metric removed versus the base branch. Removing a metric is a raise; "
                f"it needs the '{raise_label}' label on the pull request."
            )
    return failures


def summary_table(results, removed, title):
    rows = [
        f"### {title}",
        "",
        "| Metric | Count | Budget | Base budget | Count - budget | Status |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for r in results:
        delta = r.count - r.budget
        base = "-" if r.base_budget is None else str(r.base_budget)
        status = ", ".join(r.problems) if r.problems else "ok"
        mark = "x" if any(p in ("over", "slack", "raised") for p in r.problems) else "ok"
        rows.append(
            f"| `{r.name}` | {r.count} | {r.budget} | {base} | {delta:+d} | "
            f"{':x:' if mark == 'x' else ':white_check_mark:'} {status} |"
        )
    for name in removed:
        rows.append(f"| `{name}` | - | - | - | - | removed |")
    return "\n".join(rows) + "\n"


def emit(results, removed, failures, title):
    for r in results:
        print(f"{r.name}: count {r.count}, budget {r.budget}"
              + ("" if r.base_budget is None else f", base budget {r.base_budget}"))
        if "over" in r.problems and r.per_file:
            top = sorted(r.per_file.items(), key=lambda kv: (-kv[1], kv[0]))[:15]
            print("  largest contributors:")
            for path, n in top:
                print(f"    {n:5d}  {path}")
    table = summary_table(results, removed, title)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write(table + "\n")
    else:
        print("\n" + table)
    gha = os.environ.get("GITHUB_ACTIONS") == "true"
    for msg in failures:
        print(f"::error::{msg}" if gha else f"error: {msg}")
    return 1 if failures else 0


# --------------------------------------------------------------------------
# Base branch


def base_file(root: Path, base_ref: str, rel: str) -> str | None:
    """Content of rel on origin/<base_ref>, fetching the ref if needed."""
    ref = f"origin/{base_ref}"
    def have():
        return subprocess.run(["git", "-C", str(root), "rev-parse", "--verify", "-q", ref + "^{commit}"],
                              capture_output=True).returncode == 0
    if not have():
        subprocess.run(
            ["git", "-C", str(root), "fetch", "--no-tags", "--depth=1", "origin",
             f"+refs/heads/{base_ref}:refs/remotes/origin/{base_ref}"],
            capture_output=True,
        )
        if not have():
            raise ConfigError(
                f"cannot read {ref}: fetch it first (actions/checkout with fetch-depth: 0)"
            )
    proc = subprocess.run(["git", "-C", str(root), "show", f"{ref}:{rel}"], capture_output=True, text=True)
    return proc.stdout if proc.returncode == 0 else None


def parse_labels(raw: str) -> set[str]:
    raw = (raw or "").strip()
    if not raw or raw == "null":
        return set()
    try:
        val = json.loads(raw)
    except json.JSONDecodeError:
        return {s.strip() for s in raw.split(",") if s.strip()}
    return {str(v) for v in val} if isinstance(val, list) else set()


# --------------------------------------------------------------------------
# Rewriting budgets (tighten)


def set_budget(text: str, name: str, value: int) -> str:
    """Rewrite `budget = N` inside [metrics.<name>], keeping everything else."""
    header = re.compile(r'^\s*\[\s*metrics\.(?:"' + re.escape(name) + r'"|' + re.escape(name) + r")\s*\]\s*(#.*)?$")
    lines = text.splitlines(keepends=True)
    inside = False
    for i, line in enumerate(lines):
        if re.match(r"^\s*\[", line):
            inside = bool(header.match(line.rstrip("\n")))
            continue
        if inside:
            m = re.match(r"^(\s*budget\s*=\s*)\d+", line)
            if m:
                lines[i] = m.group(1) + str(value) + line[m.end():]
                return "".join(lines)
    raise ConfigError(f"could not find `budget = ...` under [metrics.{name}]")


# --------------------------------------------------------------------------
# Commands


def common_context(args):
    event = os.environ.get("GITHUB_EVENT_NAME", "")
    is_pr = bool(args.base_ref) and event in ("pull_request", "pull_request_target", "")
    return is_pr, parse_labels(args.labels)


def cmd_check(args) -> int:
    root = Path(args.root).resolve()
    cfg_path = root / args.config
    if not cfg_path.is_file():
        raise ConfigError(f"{args.config} not found in {root}")
    text = cfg_path.read_text(encoding="utf-8")
    metrics = parse_config(text, args.config)
    if args.only:
        metrics = {k: v for k, v in metrics.items() if k in args.only}
    is_pr, labels = common_context(args)
    base_budgets, removed = {}, []
    if is_pr:
        base_text = base_file(root, args.base_ref, args.config)
        if base_text is not None:
            base_budgets = budgets_of(base_text, f"origin/{args.base_ref}:{args.config}")
            removed = sorted(set(base_budgets) - set(parse_config(text, args.config)))
    files = tracked_files(root)
    rust_tests = rust_test_files(root, files) if any(m.exclude_rust_tests for m in metrics.values()) else set()
    results = []
    for m in metrics.values():
        if m.pattern is not None:
            count, per_file = count_pattern(m, root, files, rust_tests)
        else:
            count, per_file = count_command(m, root, args.action_path)
        results.append(Result(m.name, count, m.budget, base_budgets.get(m.name), per_file))
    if args.json:
        print(json.dumps({r.name: r.count for r in results}))
        return 0
    hint = lambda name, n: (
        f"set `budget = {n}` under [metrics.{name}] in {args.config} "
        f"(or run `python3 <count-ratchet>/ratchet.py tighten`)."
    )
    failures = judge(results, base_budgets, removed, is_pr, labels, args.raise_label, hint)
    return emit(results, removed, failures, args.title or f"Ratchet ({args.config})")


def cmd_tighten(args) -> int:
    root = Path(args.root).resolve()
    cfg_path = root / args.config
    text = cfg_path.read_text(encoding="utf-8")
    metrics = parse_config(text, args.config)
    files = tracked_files(root)
    rust_tests = rust_test_files(root, files) if any(m.exclude_rust_tests for m in metrics.values()) else set()
    for m in metrics.values():
        if m.pattern is not None:
            count, _ = count_pattern(m, root, files, rust_tests)
        else:
            count, _ = count_command(m, root, args.action_path)
        if count < m.budget:
            print(f"{m.name}: {m.budget} -> {count}")
            text = set_budget(text, m.name, count)
        elif count > m.budget:
            print(f"{m.name}: {count} > {m.budget}, over budget; not raised (raise it by hand, with the label)")
    cfg_path.write_text(text, encoding="utf-8")
    return 0


def cmd_number(args) -> int:
    """One metric whose budget is a bare integer in its own file (.ste-budget)."""
    root = Path(args.root).resolve()
    path = root / args.budget_file
    try:
        budget = int(path.read_text().strip())
    except (OSError, ValueError) as exc:
        raise ConfigError(f"{args.budget_file}: expected a single integer ({exc})") from exc
    is_pr, labels = common_context(args)
    base_budget = None
    if is_pr:
        base_text = base_file(root, args.base_ref, args.budget_file)
        if base_text is not None and base_text.strip().isdigit():
            base_budget = int(base_text.strip())
    results = [Result(args.name, args.count, budget, base_budget, {})]
    hint = lambda name, n: f"write {n} to {args.budget_file} (`echo {n} > {args.budget_file}`)."
    failures = judge(results, {}, [], is_pr, labels, args.raise_label, hint)
    return emit(results, [], failures, args.title or f"Ratchet ({args.budget_file})")


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    def shared(sp):
        sp.add_argument("--root", default=".")
        sp.add_argument("--base-ref", default=os.environ.get("RATCHET_BASE_REF", ""),
                        help="base branch name; enables the raise check (pull requests only)")
        sp.add_argument("--labels", default=os.environ.get("RATCHET_LABELS", ""),
                        help="pull request labels, JSON list or comma-separated")
        sp.add_argument("--raise-label", default=os.environ.get("RATCHET_RAISE_LABEL") or DEFAULT_LABEL)
        sp.add_argument("--title", default="")

    c = sub.add_parser("check", help="count every metric and apply the rules")
    shared(c)
    c.add_argument("--config", default=DEFAULT_CONFIG)
    c.add_argument("--only", nargs="*", help="limit to these metric names")
    c.add_argument("--json", action="store_true", help="print counts as JSON and exit 0")
    c.add_argument("--action-path", default=os.environ.get("RATCHET_ACTION_PATH", str(Path(__file__).parent)))
    c.set_defaults(func=cmd_check)

    t = sub.add_parser("tighten", help="lower each budget to its count (local use)")
    t.add_argument("--root", default=".")
    t.add_argument("--config", default=DEFAULT_CONFIG)
    t.add_argument("--action-path", default=str(Path(__file__).parent))
    t.set_defaults(func=cmd_tighten)

    n = sub.add_parser("number", help="one externally counted metric with a bare-integer budget file")
    shared(n)
    n.add_argument("--name", required=True)
    n.add_argument("--count", type=int, required=True)
    n.add_argument("--budget-file", required=True)
    n.set_defaults(func=cmd_number)

    args = p.parse_args(argv)
    try:
        return args.func(args)
    except ConfigError as exc:
        msg = str(exc)
        print(f"::error::{msg}" if os.environ.get("GITHUB_ACTIONS") == "true" else f"error: {msg}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
