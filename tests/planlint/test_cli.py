"""Tests for the command line and its exit codes.

Exit 0 is clean. Any finding exits non-zero. A lint that found no input to
examine exits non-zero too: nothing to check is never a pass.
"""

import io
import unittest

from tests.planlint.support import fixture_path

from planlint import cli


def run(argv):
    out = io.StringIO()
    code = cli.main(argv, stream=out)
    return code, out.getvalue()


class ExitCodeTest(unittest.TestCase):
    def test_a_clean_plan_exits_zero(self):
        code, text = run(["--plan", str(fixture_path("clean_plan.md"))])

        self.assertEqual(code, 0)
        self.assertIn("graph: clean", text)
        self.assertIn("ALL LINTS CLEAN", text)

    def test_a_plan_with_a_cycle_exits_non_zero(self):
        code, text = run(["--plan", str(fixture_path("neg_graph_cycle.md"))])

        self.assertEqual(code, 1)
        self.assertIn("dependency-cycle", text)

    def test_a_lint_with_no_input_exits_non_zero(self):
        code, text = run(["--plan", str(fixture_path("neg_graph_cycle.md")), "--only", "counts"])

        self.assertEqual(code, 1)
        self.assertIn("no-input", text)

    def test_only_selects_one_lint(self):
        code, text = run(["--plan", str(fixture_path("clean_plan.md")), "--only", "graph"])

        self.assertEqual(code, 0)
        self.assertIn("graph: clean", text)
        self.assertNotIn("waves:", text)

    def test_an_unknown_lint_name_exits_non_zero_and_names_the_choices(self):
        code, text = run(["--plan", str(fixture_path("clean_plan.md")), "--only", "ghost"])

        self.assertEqual(code, 2)
        self.assertIn("unknown lint 'ghost'", text)
        self.assertIn("graph", text)

    def test_the_repository_lint_runs_against_a_tree(self):
        code, text = run(
            [
                "--plan", str(fixture_path("clean_plan.md")),
                "--repo", str(fixture_path("repo_public_bad")),
                "--only", "payload",
            ]
        )

        self.assertEqual(code, 1)
        self.assertIn("no-clavia-upload", text)

    def test_payload_without_a_repository_argument_exits_non_zero(self):
        code, text = run(
            ["--plan", str(fixture_path("clean_plan.md")), "--only", "payload"]
        )

        self.assertEqual(code, 2)
        self.assertIn("--repo is required", text)

    def test_a_missing_plan_file_exits_non_zero(self):
        code, text = run(["--plan", str(fixture_path("no_such_plan.md"))])

        self.assertEqual(code, 2)
        self.assertIn("no such plan document", text)


if __name__ == "__main__":
    unittest.main()
