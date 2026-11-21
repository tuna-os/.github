#!/usr/bin/env python3
"""Self-tests for count-ratchet. Run: python3 test_ratchet.py"""

import contextlib
import io
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import ratchet  # noqa: E402


def git(root, *args):
    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)


class Repo:
    """A throwaway git repo with an `origin/main` to compare against."""

    def __init__(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        git(self.root, "init", "-q", "-b", "main")
        git(self.root, "config", "user.email", "t@example.com")
        git(self.root, "config", "user.name", "t")
        git(self.root, "config", "commit.gpgsign", "false")

    def write(self, rel, text):
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(textwrap.dedent(text))
        git(self.root, "add", rel)

    def commit_as_base(self):
        git(self.root, "commit", "-q", "-m", "base", "--allow-empty")
        git(self.root, "update-ref", "refs/remotes/origin/main", "HEAD")

    def run(self, *args, env=None):
        out = io.StringIO()
        old = {k: os.environ.get(k) for k in ("GITHUB_STEP_SUMMARY", "GITHUB_ACTIONS", "GITHUB_EVENT_NAME")}
        os.environ.pop("GITHUB_STEP_SUMMARY", None)
        os.environ.pop("GITHUB_ACTIONS", None)
        os.environ["GITHUB_EVENT_NAME"] = (env or {}).get("GITHUB_EVENT_NAME", "pull_request")
        try:
            with contextlib.redirect_stdout(out):
                code = ratchet.main([args[0], "--root", str(self.root), *args[1:]])
        finally:
            for k, v in old.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v
        return code, out.getvalue()

    def close(self):
        self.tmp.cleanup()


CONFIG = """\
[defaults]
exclude = ["**/tests/**", "**/*_test.rs"]

[metrics.unwrap]
description = "non-test .unwrap()"
pattern = '\\.unwrap\\(\\)'
include = ["**/*.rs"]
exclude-rust-tests = true
budget = {budget}
"""

SRC = """\
fn a() { x.unwrap(); y.unwrap(); }

#[cfg(test)]
mod tests {
    fn t() { z.unwrap(); }
}
"""


class GlobTests(unittest.TestCase):
    def test_doublestar_matches_zero_or_more_dirs(self):
        g = ratchet.glob_to_regex("**/tests/**")
        self.assertTrue(g.match("tests/a.rs"))
        self.assertTrue(g.match("crates/x/tests/a/b.rs"))
        self.assertFalse(g.match("crates/x/src/tests.rs"))

    def test_star_stays_in_segment(self):
        g = ratchet.glob_to_regex("src/*.rs")
        self.assertTrue(g.match("src/a.rs"))
        self.assertFalse(g.match("src/a/b.rs"))

    def test_bare_name_matches_any_depth(self):
        g = ratchet.glob_to_regex("*_test.go")
        self.assertTrue(g.match("a/b/c_test.go"))
        self.assertFalse(g.match("a/b/c.go"))


class RuleTests(unittest.TestCase):
    def setUp(self):
        self.repo = Repo()
        self.repo.write("src/lib.rs", SRC)
        self.repo.write("tests/it.rs", "fn t() { q.unwrap(); }\n")
        self.repo.write("src/helper_test.rs", "fn t() { q.unwrap(); }\n")

    def tearDown(self):
        self.repo.close()

    def base(self, budget):
        self.repo.write(".ratchet.toml", CONFIG.format(budget=budget))
        self.repo.commit_as_base()

    def check(self, budget, labels="[]", base_ref="main", event="pull_request"):
        self.repo.write(".ratchet.toml", CONFIG.format(budget=budget))
        return self.repo.run("check", "--base-ref", base_ref, "--labels", labels,
                             env={"GITHUB_EVENT_NAME": event})

    def test_exact_budget_passes_and_excludes_tests(self):
        self.base(2)
        code, out = self.check(2)
        self.assertEqual(code, 0, out)
        self.assertIn("unwrap: count 2, budget 2", out)

    def test_over_budget_fails_and_names_files(self):
        self.base(1)
        code, out = self.check(1)
        self.assertEqual(code, 1)
        self.assertIn("2 > budget 1", out)
        self.assertIn("src/lib.rs", out)

    def test_slack_fails_with_exact_edit(self):
        self.base(5)
        code, out = self.check(5)
        self.assertEqual(code, 1)
        self.assertIn("set `budget = 2` under [metrics.unwrap]", out)

    def test_raise_without_label_fails(self):
        self.repo.write("src/more.rs", "fn b() { a.unwrap(); }\n")
        self.base(2)
        code, out = self.check(3)
        self.assertEqual(code, 1)
        self.assertIn("budget raised 2 -> 3", out)

    def test_raise_with_label_passes(self):
        self.repo.write("src/more.rs", "fn b() { a.unwrap(); }\n")
        self.base(2)
        code, out = self.check(3, labels='["ratchet-raise"]')
        self.assertEqual(code, 0, out)

    def test_raise_is_not_checked_on_push(self):
        self.repo.write("src/more.rs", "fn b() { a.unwrap(); }\n")
        self.base(2)
        code, out = self.check(3, base_ref="", event="push")
        self.assertEqual(code, 0, out)

    def test_lowering_passes(self):
        self.base(3)
        code, out = self.check(2)
        self.assertEqual(code, 0, out)

    def test_removing_a_metric_needs_the_label(self):
        self.base(2)
        self.repo.write(".ratchet.toml", textwrap.dedent("""\
            [metrics.other]
            pattern = 'nothing-matches-this'
            budget = 0
        """))
        code, out = self.repo.run("check", "--base-ref", "main", "--labels", "[]")
        self.assertEqual(code, 1)
        self.assertIn("unwrap: metric removed", out)

    # A pull request that adds a counted call and edits what the metric
    # counts, so the count and the budget both stay at the base value.
    def redefine(self, old, new, labels="[]", base_ref="main", event="pull_request"):
        self.base(2)
        self.repo.write("src/more.rs", "fn b() { a.unwrap(); }\n")
        text = CONFIG.format(budget=2)
        self.assertIn(old, text)
        self.repo.write(".ratchet.toml", text.replace(old, new))
        return self.repo.run("check", "--base-ref", base_ref, "--labels", labels,
                             env={"GITHUB_EVENT_NAME": event})

    def test_excluding_the_new_code_needs_the_label(self):
        code, out = self.redefine(
            'include = ["**/*.rs"]',
            'include = ["**/*.rs"]\nexclude = ["src/more.rs", "**/tests/**", "**/*_test.rs"]',
        )
        self.assertEqual(code, 1, out)
        self.assertIn("unwrap: what the metric counts changed", out)
        self.assertIn("redefined", out)

    def test_excluding_the_new_code_in_defaults_needs_the_label(self):
        code, out = self.redefine('exclude = ["**/tests/**", "**/*_test.rs"]',
                                  'exclude = ["**/tests/**", "**/*_test.rs", "src/more.rs"]')
        self.assertEqual(code, 1, out)
        self.assertIn("unwrap: what the metric counts changed", out)

    def test_narrowing_the_include_needs_the_label(self):
        code, out = self.redefine('include = ["**/*.rs"]', 'include = ["src/lib.rs"]')
        self.assertEqual(code, 1, out)
        self.assertIn("unwrap: what the metric counts changed", out)

    def test_new_pattern_needs_the_label(self):
        code, out = self.redefine("pattern = '\\.unwrap\\(\\)'",
                                  "pattern = '\\.unwrap\\(\\);\\s*y'")
        self.assertEqual(code, 1, out)
        self.assertIn("unwrap: what the metric counts changed", out)

    def test_pattern_replaced_by_command_needs_the_label(self):
        self.base(2)
        self.repo.write("src/more.rs", "fn b() { a.unwrap(); }\n")
        self.repo.write(".ratchet.toml", """\
            [metrics.unwrap]
            command = 'echo 2'
            budget = 2
        """)
        code, out = self.repo.run("check", "--base-ref", "main", "--labels", "[]")
        self.assertEqual(code, 1, out)
        self.assertIn("unwrap: what the metric counts changed", out)

    def test_redefinition_with_label_passes(self):
        code, out = self.redefine('include = ["**/*.rs"]', 'include = ["src/lib.rs"]',
                                  labels='["ratchet-raise"]')
        self.assertEqual(code, 0, out)
        self.assertIn("redefined (label)", out)

    def test_redefinition_is_not_checked_on_push(self):
        code, out = self.redefine('include = ["**/*.rs"]', 'include = ["src/lib.rs"]',
                                  base_ref="", event="push")
        self.assertEqual(code, 0, out)

    def test_same_definition_written_another_way_passes(self):
        # A new description, a reordered glob list and a default copied into
        # the metric count the same files.
        self.base(2)
        self.repo.write(".ratchet.toml", """\
            [defaults]
            exclude = ["**/*_test.rs", "**/tests/**"]

            [metrics.unwrap]
            description = "reworded"
            pattern = '\\.unwrap\\(\\)'
            include = ["**/*.rs"]
            exclude = ["**/tests/**", "**/*_test.rs"]
            exclude-rust-tests = true
            budget = 2
        """)
        code, out = self.repo.run("check", "--base-ref", "main", "--labels", "[]")
        self.assertEqual(code, 0, out)

    def test_new_config_without_base_passes(self):
        self.repo.commit_as_base()
        code, out = self.check(2)
        self.assertEqual(code, 0, out)

    def test_cfg_test_declared_module_file_is_excluded(self):
        self.repo.write("src/main.rs", "#[cfg(test)]\nmod unit;\nfn m() { a.unwrap(); }\n")
        self.repo.write("src/unit.rs", "fn t() { b.unwrap(); c.unwrap(); }\n")
        self.base(3)
        code, out = self.check(3)
        self.assertEqual(code, 0, out)

    def test_cfg_all_test_module_is_stripped(self):
        self.repo.write("src/unix.rs", "fn u() {}\n#[cfg(all(test, unix))]\nmod tests { fn t() { a.unwrap(); } }\n")
        self.base(2)
        code, out = self.check(2)
        self.assertEqual(code, 0, out)

    def test_config_file_is_not_counted(self):
        # The description matches the pattern; the file must still not count.
        self.repo.write(".ratchet.toml", """\
            [metrics.todo]
            description = "TODO markers"
            pattern = 'TODO'
            budget = 1
        """)
        self.repo.write("a.txt", "TODO\n")
        code, out = self.repo.run("check")
        self.assertEqual(code, 0, out)

    def test_tighten_rewrites_only_the_budget(self):
        self.repo.write(".ratchet.toml", CONFIG.format(budget=9) + "# trailing comment\n")
        code, _ = self.repo.run("tighten")
        self.assertEqual(code, 0)
        text = (self.repo.root / ".ratchet.toml").read_text()
        self.assertIn("budget = 2\n", text)
        self.assertIn("# trailing comment", text)


class CommandMetricTests(unittest.TestCase):
    def setUp(self):
        self.repo = Repo()

    def tearDown(self):
        self.repo.close()

    def test_command_last_line_is_the_count(self):
        self.repo.write(".ratchet.toml", """\
            [metrics.lines]
            command = "printf 'detail\\n3\\n'"
            budget = 3
        """)
        code, out = self.repo.run("check")
        self.assertEqual(code, 0, out)
        self.assertIn("[lines] detail", out)

    def test_failing_command_is_a_config_error(self):
        self.repo.write(".ratchet.toml", """\
            [metrics.broken]
            command = "exit 3"
            budget = 0
        """)
        code, out = self.repo.run("check")
        self.assertEqual(code, 2)
        self.assertIn("command must exit 0", out)

    def test_deny_review_dates_helper(self):
        self.repo.write("deny.toml", """\
            [advisories]
            ignore = [
              "RUSTSEC-0000-0001",
              { id = "RUSTSEC-0000-0002", reason = "no date here" },
              { id = "RUSTSEC-0000-0003", reason = "fine; review by 2999-01-01" },
              { crate = "zip@8.6.0", reason = "fine; review by 2999-01-01" },
            ]
        """)
        self.repo.write(".ratchet.toml", """\
            [metrics.deny-undated]
            command = 'python3 "$RATCHET_ACTION_PATH/checks/deny_review_dates.py" deny.toml'
            budget = 2
        """)
        code, out = self.repo.run("check", "--action-path", str(HERE))
        self.assertEqual(code, 0, out)
        self.assertIn("RUSTSEC-0000-0002", out)


class ConfigTests(unittest.TestCase):
    def test_pattern_and_command_are_exclusive(self):
        with self.assertRaises(ratchet.ConfigError):
            ratchet.parse_config('[metrics.x]\npattern = "a"\ncommand = "b"\nbudget = 0\n')

    def test_unknown_key_rejected(self):
        with self.assertRaises(ratchet.ConfigError):
            ratchet.parse_config('[metrics.x]\npattern = "a"\nbudgte = 0\nbudget = 0\n')

    def test_budget_required(self):
        with self.assertRaises(ratchet.ConfigError):
            ratchet.parse_config('[metrics.x]\npattern = "a"\n')


class NumberModeTests(unittest.TestCase):
    """The mode ste-lint uses: an external count against a bare-integer file."""

    def setUp(self):
        self.repo = Repo()
        self.repo.write(".ste-budget", "10\n")
        self.repo.commit_as_base()

    def tearDown(self):
        self.repo.close()

    def number(self, count, budget, labels="[]"):
        self.repo.write(".ste-budget", f"{budget}\n")
        return self.repo.run("number", "--name", "ste", "--count", str(count),
                             "--budget-file", ".ste-budget", "--base-ref", "main", "--labels", labels)

    def test_equal_passes(self):
        self.assertEqual(self.number(10, 10)[0], 0)

    def test_slack_names_new_value(self):
        code, out = self.number(8, 10)
        self.assertEqual(code, 1)
        self.assertIn("echo 8 > .ste-budget", out)

    def test_raise_needs_label(self):
        self.assertEqual(self.number(12, 12)[0], 1)
        self.assertEqual(self.number(12, 12, labels="ratchet-raise")[0], 0)


if __name__ == "__main__":
    unittest.main(verbosity=1)
