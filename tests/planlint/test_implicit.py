"""Tests for the implicit-dependency lint.

A task that writes into, or reads from, an artifact another task creates, where
no `Depends:` edge exists. The heuristic reports candidates with evidence; a
human adjudicates. Precision matters less than not missing this class.
"""

import unittest

from tests.planlint.support import load_fixture

from planlint import implicit
from planlint.document import PlanDocument


def run(name):
    return implicit.run(load_fixture(name))


class ImplicitLintTest(unittest.TestCase):
    def test_the_clean_plan_reports_nothing(self):
        result = run("clean_plan.md")

        self.assertEqual(result.findings, [])
        # `tests/CMakeLists.txt`, `conformance/corpus/*.json`, `testdata/synth/`
        # and `testdata/beta/`. The two paths that two tasks claim are an
        # ownership question and not an implicit edge, so they are not tracked.
        self.assertEqual(result.examined, 4)

    def test_an_undeclared_consumer_of_a_created_directory_is_reported(self):
        result = run("neg_implicit_dependency.md")

        self.assertIn(
            (
                "implicit-dependency",
                "BBB-1",
                "BBB-1 names `corpus/data/`, `corpus/data/MANIFEST.txt`, which AAA-1 "
                "creates; BBB-1 declares no path to AAA-1",
            ),
            [(f.rule, f.task, f.evidence) for f in result.findings],
        )

    def test_the_edge_that_would_close_a_cycle_is_reported_as_its_own_rule(self):
        result = run("neg_implicit_dependency.md")

        self.assertIn(
            (
                "implicit-dependency-would-cycle",
                "DDD-1",
                "DDD-1 names `axiomantic/store`, which CCC-1 creates; DDD-1 declares "
                "no path to CCC-1, and CCC-1 already depends on DDD-1, so the missing "
                "edge would close a cycle",
            ),
            [(f.rule, f.task, f.evidence) for f in result.findings],
        )

    def test_a_consumer_that_declares_the_edge_is_not_reported(self):
        result = run("neg_implicit_dependency.md")

        # A lint that reported nothing would also satisfy the line below.
        self.assertEqual(sorted(f.task for f in result.findings), ["BBB-1", "DDD-1"])
        self.assertNotIn("EEE-1", {f.task for f in result.findings})

    def test_the_negative_fixture_reports_exactly_these_two(self):
        result = run("neg_implicit_dependency.md")

        self.assertEqual(
            sorted((f.rule, f.task) for f in result.findings),
            [
                ("implicit-dependency", "BBB-1"),
                ("implicit-dependency-would-cycle", "DDD-1"),
            ],
        )

    def test_a_document_with_no_artifact_to_track_is_a_hard_error(self):
        result = implicit.run(
            PlanDocument.from_text(
                "**AAA-1 · A task** — T0\n"
                "Files: `src/one.cpp`\n"
                "Depends: none\n"
                "Check: `ctest --test-dir build --no-tests=error -R t0_a`\n",
                name="inline",
            )
        )

        self.assertEqual(
            [(f.rule, f.message) for f in result.findings],
            [("no-input", "the implicit-dependency lint examined 0 tracked artifacts")],
        )


if __name__ == "__main__":
    unittest.main()
