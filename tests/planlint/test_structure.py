"""Tests for the structure lint — defect L-5, the self-reporting half.

Fixing the scanner stops a broken fence from blinding the lints. It does not
tell anybody the markup is broken, and a scanner that quietly copes is one
edit away from quietly coping with something it should not.

This lint makes the class self-reporting. A task body whose backticks do not
pair, and a fence with no partner, are findings in their own right. Neither is
allowed to present as a clean result.
"""

import unittest

from tests.planlint.support import load_fixture

from planlint import structure
from planlint.document import PlanDocument


def run(name):
    return structure.run(load_fixture(name))


def rows(result):
    return sorted((f.rule, f.task, f.line, f.evidence) for f in result.findings)


class UnmatchedBacktickTest(unittest.TestCase):
    def test_a_task_body_with_an_odd_backtick_is_reported(self):
        self.assertEqual(
            rows(run("neg_structure_unmatched_backtick.md")),
            [
                (
                    "unmatched-backtick",
                    "DDD-1",
                    109,
                    "line 109 carries 1 backtick with no partner on its own line: "
                    "`Check: `pytest tools/test_delta.py`. The suite carries a "
                    "failing case of its own. The forwarding flag is spelled "
                    "`--group.`. Every name after it in this body reads as prose",
                )
            ],
        )

    def test_the_clean_plan_reports_nothing(self):
        self.assertEqual(run("clean_plan.md").findings, [])

    def test_a_fence_never_counts_as_an_unmatched_backtick(self):
        """A fence marker is three backticks and an odd count. Reading the
        markers as inline ticks would report every fenced task in the plan,
        which is the false positive that trains a reader to ignore a rule."""
        doc = PlanDocument.from_text(
            "**AAA-1 · A task** — T0\n"
            "Files: `src/one.cpp`\n"
            "Depends: none\n"
            "Check: The measurement is printed:\n"
            "```\n"
            "$ ctest --test-dir build --no-tests=error -R ^t0_one$\n"
            "```\n",
            name="inline",
        )

        self.assertEqual(structure.run(doc).findings, [])


class UnclosedFenceTest(unittest.TestCase):
    def test_a_fence_with_no_partner_is_reported(self):
        self.assertEqual(
            rows(run("neg_structure_unclosed_fence.md")),
            [
                (
                    "unclosed-fence",
                    "",
                    137,
                    "line 137 opens a fenced block and no line below it closes "
                    "the fence; every fenced-block rule below line 137 reads the "
                    "document with the wrong boundaries",
                )
            ],
        )

    def test_an_unclosed_fence_still_leaves_every_task_visible(self):
        """The scanner refuses to let a broken fence run to the end of the
        text, because that would hide every task below it. The rule reports the
        breakage instead. Both halves are asserted, or the report is the only
        evidence that anything survived."""
        doc = load_fixture("neg_structure_unclosed_fence.md")
        clean = load_fixture("clean_plan.md")

        self.assertEqual(
            [task.ident for task in doc.tasks], [task.ident for task in clean.tasks]
        )


class NoInputTest(unittest.TestCase):
    def test_a_document_with_no_task_block_is_a_hard_error(self):
        result = structure.run(
            PlanDocument.from_text("# A document with no task\n", name="inline")
        )

        self.assertEqual(
            [(f.rule, f.message, f.severity) for f in result.findings],
            [("no-input", "the structure lint examined 0 task bodies", "ERROR")],
        )


if __name__ == "__main__":
    unittest.main()
