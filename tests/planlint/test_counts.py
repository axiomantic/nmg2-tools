"""Tests for the self-consistency lint: every count the plan states about
itself must match its own rows."""

import unittest

from tests.planlint.support import load_fixture

from planlint import counts
from planlint.document import PlanDocument


def run(name):
    return counts.run(load_fixture(name))


class NumberWordTest(unittest.TestCase):
    def test_a_digit_and_a_word_both_read_as_the_same_number(self):
        self.assertEqual(counts.as_number("5"), 5)
        self.assertEqual(counts.as_number("five"), 5)
        self.assertEqual(counts.as_number("Fourteen"), 14)
        self.assertIsNone(counts.as_number("several"))


class CountsLintTest(unittest.TestCase):
    def test_the_clean_plan_reports_nothing(self):
        result = run("clean_plan.md")

        self.assertEqual(result.findings, [])
        # Five track rows, the total row, the conditional-task count and the
        # cross-track edge count.
        self.assertEqual(result.examined, 8)

    def test_every_miscount_is_reported_and_nothing_else(self):
        result = run("neg_counts.md")

        self.assertEqual(
            sorted((f.rule, f.evidence) for f in result.findings),
            [
                (
                    "conditional-count-mismatch",
                    "the plan says 4 conditional tasks; section 24.4's table holds 1",
                ),
                (
                    "cross-track-edge-count-mismatch",
                    "section 7.6 assertion 7 says 3 cross-track edges inside one wave; "
                    "section 7.3's column holds 1 (BBB-1 → CCC-1)",
                ),
                (
                    "total-count-mismatch",
                    "section 24.1 says 9 task blocks; the document holds 4",
                ),
                (
                    "total-is-not-the-sum",
                    "section 24.1's track rows sum to 5; its total row says 9",
                ),
                (
                    "track-count-mismatch",
                    "section 24.1 says track AAA has 3 tasks; the document holds 2 "
                    "(AAA-1, AAA-2)",
                ),
            ],
        )

    def test_a_document_that_states_no_count_is_a_hard_error(self):
        result = counts.run(
            PlanDocument.from_text(
                "**AAA-1 · A task** — T0\nDepends: none\nCheck: `ctest`\n", name="inline"
            )
        )

        self.assertEqual(
            [(f.rule, f.message) for f in result.findings],
            [("no-input", "the counts lint examined 0 stated counts")],
        )


if __name__ == "__main__":
    unittest.main()
