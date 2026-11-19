#!/usr/bin/env python3
"""Exercise publish-flatpak.yml's inline rolling-channel guards.

tuna-os/Tavern#195: the rolling channel -- the arch-independent ``:latest`` image
and the central Flatpak index -- must be skipped on a release-tag dispatch.
publish-flatpak.yml enforces that with two inline guards:

  * a bash ``if`` around the ``:latest`` push in the "Push OCI to registry" step,
  * a GHA ``if:`` expression on the "Update central index" step.

The unit test for publish-rolling-channel.py pins the *contract* (which writes
are rolling-channel writes), but it never runs the workflow's *guards*: a
developer could change one guard and the contract test would still pass. This
test parses both guards straight out of the workflow file and asserts they
evaluate false on ``refs/tags/*`` and true otherwise, so the guards cannot drift
from the contract.

Plain python3, no test framework -- matches how scripts/ is run in CI.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "publish-flatpak.yml"

TAG_REF = "refs/tags/v0.1.64"
BRANCH_REF = "refs/heads/main"


def _load() -> dict:
    doc = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8")) or {}
    if not doc:
        raise AssertionError(f"{WORKFLOW} did not load")
    return doc


def _workflow_steps(doc: dict) -> list[dict]:
    for job in doc.get("jobs", {}).values() or []:
        yield from job.get("steps", []) or []


def _push_step(doc: dict) -> dict:
    for step in _workflow_steps(doc):
        if step.get("name") == "Push OCI to registry":
            return step
    raise AssertionError("step 'Push OCI to registry' not found")


def _index_step(doc: dict) -> dict:
    for step in _workflow_steps(doc):
        if str(step.get("name", "")).startswith("Update central index"):
            return step
    raise AssertionError("step 'Update central index' not found")


def _latest_guard_line(run_block: str) -> str:
    """Return the rolling ``:latest`` push guard line from the push step's run block.

    Distinguished from the version-tag guard (``== refs/tags/*``) by the rolling
    guard's ``!= refs/tags/*`` and its ``[ "$arch" = "$PRIMARY" ]`` clause.
    """
    for raw in run_block.splitlines():
        line = raw.strip()
        if (
            line.startswith('if [[ "$GITHUB_REF"')
            and "!= refs/tags/*" in line
            and 'PRIMARY"' in line
        ):
            return line
    raise AssertionError("rolling :latest guard not found in push step run block")


def _bash_guard_runs(guard_line: str, github_ref: str, arch: str, primary: str) -> bool:
    """Evaluate the ``:latest`` guard exactly as the workflow's bash step would.

    Returns True when the ``:latest`` push runs, False when it is skipped. Running
    the real guard under bash is what makes this a guard test, not a copy of the
    contract.
    """
    stripped = guard_line.strip()
    if not stripped.endswith("; then"):
        raise AssertionError(f"unexpected guard line form: {guard_line!r}")
    condition = stripped[len("if "):-len("; then")].strip()
    probe = f"if {condition}; then echo run; else echo skip; fi"
    env = {"GITHUB_REF": github_ref, "arch": arch, "PRIMARY": primary}
    result = subprocess.run(["bash", "-c", probe], env=env, capture_output=True, text=True)
    if result.returncode != 0:
        raise AssertionError(f"guard probe failed: {result.stderr.strip()}")
    return result.stdout.strip() == "run"


def _gha_if_runs(expr: str, github_ref: str) -> bool:
    """Evaluate a publish-flatpak.yml rolling-guard GHA ``if:`` expression.

    Handles the subset the workflow uses (``!`` prefix and
    ``startsWith(github.ref, 'literal')``). Anything else raises, so a guard that
    drifts past this expression form fails the test loudly rather than passing.
    """
    text = expr.strip()
    if text.startswith("${{"):
        text = text[len("${{"):].strip()
    if text.endswith("}}"):
        text = text[:-2].strip()
    return _eval_gha_expr(text, github_ref)


def _eval_gha_expr(expr: str, github_ref: str) -> bool:
    expr = expr.strip()
    if expr.startswith("!"):
        return not _eval_gha_expr(expr[1:].strip(), github_ref)
    if expr.startswith("startsWith(") and "github.ref" in expr:
        literal = expr.split("'", 1)[1].rsplit("'", 1)[0]
        return github_ref.startswith(literal)
    raise AssertionError(f"unsupported GHA if expression in guard: {expr!r}")


def _check(guard_name: str, runs, ref: str, should_run: bool) -> str | None:
    actually = runs(ref)
    if actually != should_run:
        return (
            f"{guard_name} on {ref}: expected {'run' if should_run else 'skip'}, "
            f"{'ran' if actually else 'skipped'}"
        )
    return None


def main() -> int:
    doc = _load()

    push_step = _push_step(doc)
    guard_line = _latest_guard_line(push_step.get("run", ""))
    index_step = _index_step(doc)
    if_expr = index_step.get("if")
    if not if_expr:
        raise AssertionError("central index step has no if: expression")

    failures: list[str] = []
    # Rolling :latest push: skip on a tag, run (from primary) on a branch.
    for ref, should_run in ((TAG_REF, False), (BRANCH_REF, True)):
        problem = _check(
            ":latest guard",
            lambda r, ref=ref: _bash_guard_runs(guard_line, r, "x86_64", "x86_64"),
            ref,
            should_run,
        )
        if problem:
            failures.append(problem)

    # Central index: skip on a tag, run on a branch.
    for ref, should_run in ((TAG_REF, False), (BRANCH_REF, True)):
        problem = _check(
            "central-index guard",
            lambda r, ref=ref: _gha_if_runs(if_expr, r),
            ref,
            should_run,
        )
        if problem:
            failures.append(problem)

    # The non-primary-arch :latest guard must never push :latest, on any ref.
    if _bash_guard_runs(guard_line, BRANCH_REF, "aarch64", "x86_64"):
        failures.append(":latest guard pushed :latest from a non-primary arch on a branch")

    if failures:
        print("FAIL: publish-flatpak rolling guards regressed:")
        for f in failures:
            print(f"  - {f}")
        return 1

    print("OK: :latest and central-index guards skip on refs/tags/*, run otherwise.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
