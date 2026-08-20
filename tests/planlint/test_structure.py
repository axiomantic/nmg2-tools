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


UNDECIDED_MESSAGE = (
    "a run of table rows carries no delimiter row, so the table states no "
    "column count and the cell count of every row in it is UNDECIDED. This is "
    "reported rather than passed, because a rule that skipped the run and a "
    "rule that found it correct print the same result. Markdown fixes a "
    "table's column count at its delimiter row, and a continuation row written "
    "below a blank line is the shape that carries none"
)


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


class DoneMarkerFormTest(unittest.TestCase):
    """A completion marker a line-anchored pattern cannot see.

    Section 24.6 row W3-20 takes a marker census with `/^\\*\\*DONE/` and states
    why the anchor is there: it must read task-level markers only and never a
    `**DONE` inside a half-state table row. The anchor does that, and it also
    misses every task-level marker written behind a lead-in — silently, as a
    smaller number.

    Repairing the count would leave the next pattern free to be wrong the same
    way. This rule removes the freedom: a marker the anchored form misses is a
    finding, so a document this lint passes is a document on which the anchored
    form and the wide form return the same set.
    """

    def doc(self, body):
        return PlanDocument.from_text(
            "## 9. The tasks\n"
            "\n"
            "**DSP-2 · The two new DMA request sources** — T0\n"
            "Files: `src/dma.cpp`\n"
            "Depends: none\n"
            "Check: `ctest --test-dir build --no-tests=error -R t0_dma`\n"
            f"{body}\n",
            name="inline",
        )

    def test_a_marker_that_does_not_open_its_line_is_reported(self):
        result = structure.run(
            self.doc("Note: **DONE on 2026-08-06, commit `51903e5c`.**")
        )

        self.assertEqual(
            [
                (f.rule, f.task, f.section, f.line, f.severity, f.evidence)
                for f in result.findings
            ],
            [
                (
                    "done-marker-not-line-anchored",
                    "DSP-2",
                    "9. The tasks",
                    7,
                    "ERROR",
                    "line 7 carries a `**DONE` marker that does not open the "
                    "line: `Note: **DONE on 2026-08-06, commit `51903e5c`.**`. "
                    "A census anchored at the start of the line reads this "
                    "task as unmarked",
                )
            ],
        )

    def test_a_marker_that_opens_its_line_is_not_reported(self):
        result = structure.run(self.doc("**DONE on 2026-08-06, commit `51903e5c`.**"))

        self.assertEqual(result.findings, [])

    def test_a_marker_inside_a_table_row_is_not_reported(self):
        """The exclusion W3-20 states in its own words. REPO-15's half-state
        rows carry a `**DONE` that belongs to a half of the task, and a rule
        that reported them would fire on the one case the anchor exists for."""
        result = structure.run(
            self.doc(
                "| Half | State | Evidence |\n"
                "|---|---|---|\n"
                "| The operator-gated extraction | **DONE** | one commit |"
            )
        )

        self.assertEqual(result.findings, [])

    def test_the_clean_plan_reports_no_marker_finding(self):
        self.assertEqual(run("clean_plan.md").findings, [])


class TableRowColumnCountTest(unittest.TestCase):
    """A table row that renders with the wrong number of cells.

    Markdown fixes the column count at the DELIMITER row. A row carrying an
    unescaped `|` inside a cell splits there, so a reader and a lint read the
    wrong text in the wrong column, and neither of them is told.

    The escaped spelling is the repair AND the control. A rule that counted raw
    pipes would report the correct row beside the broken one, so the fixture
    carries both and this test asserts that only one is reported.
    """

    def test_a_row_with_an_unescaped_pipe_inside_a_cell_is_reported(self):
        result = run("neg_structure_table_row_column_count.md")

        self.assertEqual(
            [
                (f.rule, f.task, f.section, f.line, f.severity, f.message, f.evidence)
                for f in result.findings
            ],
            [
                (
                    "table-row-column-count",
                    "",
                    "6. The milestone ladder",
                    30,
                    "ERROR",
                    "a table row carries a different number of unescaped `|` "
                    "characters than the delimiter row of its own table. "
                    "Markdown fixes the column count at the delimiter row, so "
                    "this row renders with the wrong number of cells and every "
                    "reader — a person and a lint — reads the wrong text in the "
                    "wrong column",
                    "line 30 carries 6 unescaped `|` characters and the "
                    "delimiter row at line 28 carries 5. The row opens `**M2**` "
                    "and a `|` that belongs to a cell is written `\\|`",
                ),
                (
                    "table-column-count-undecided",
                    "",
                    "6. The milestone ladder",
                    33,
                    "WARNING",
                    UNDECIDED_MESSAGE,
                    "line 33 carries 1 table row and no delimiter row, so this "
                    "run states no column count and `table-row-column-count` "
                    "decides nothing about it. The run opens `**M4**`",
                ),
            ],
        )

    def test_the_clean_plan_reports_nothing(self):
        self.assertEqual(run("clean_plan.md").findings, [])

    def test_a_table_inside_a_fence_states_no_norm_and_is_not_read(self):
        """A fenced block is a quotation. Reading a quoted table would report a
        row the document never renders as a table at all."""
        doc = PlanDocument.from_text(
            "**AAA-1 · A task** — T0\n"
            "Files: `src/one.cpp`\n"
            "Depends: none\n"
            "Check: The shape a broken row has is quoted here:\n"
            "```\n"
            "| # | What it is |\n"
            "|---|---|\n"
            "| W2-1 | a raw | pipe |\n"
            "```\n",
            name="inline",
        )

        self.assertEqual(structure.run(doc).findings, [])

    def test_a_table_with_no_delimiter_row_is_reported_as_undecided(self):
        """The undecided branch, REPORTED rather than skipped in silence.

        The norm is the delimiter row's own count, so a run of table rows that
        carries no delimiter row states no column count and this rule decides
        nothing about it. A skip and a pass print the same result, so the skip
        is a finding under its own rule identity.
        """
        doc = PlanDocument.from_text(
            "**AAA-1 · A task** — T0\n"
            "Files: `src/one.cpp`\n"
            "Depends: none\n"
            "Check: `ctest --test-dir build --no-tests=error -R t0_one`\n"
            "\n"
            "| **M4** | a row with | no delimiter row above it |\n",
            name="inline",
        )

        self.assertEqual(
            [
                (f.rule, f.task, f.section, f.line, f.severity, f.message, f.evidence)
                for f in structure.run(doc).findings
            ],
            [
                (
                    "table-column-count-undecided",
                    "",
                    "",
                    6,
                    "WARNING",
                    UNDECIDED_MESSAGE,
                    "line 6 carries 1 table row and no delimiter row, so this "
                    "run states no column count and `table-row-column-count` "
                    "decides nothing about it. The run opens `**M4**`",
                )
            ],
        )

    def test_a_multi_row_table_with_no_delimiter_row_names_its_whole_span(self):
        """The plan's case is one row. The rule must report the shape it
        cannot decide and not the one instance of it this document holds, so
        the span and the row count are asserted on a run longer than one."""
        doc = PlanDocument.from_text(
            "**AAA-1 · A task** — T0\n"
            "Files: `src/one.cpp`\n"
            "Depends: none\n"
            "Check: `ctest --test-dir build --no-tests=error -R t0_one`\n"
            "\n"
            "| **M4** | a run of rows |\n"
            "| **M5** | with no delimiter row anywhere in it |\n"
            "| **M6** | so no row of it states a column count |\n",
            name="inline",
        )

        self.assertEqual(
            [
                (f.rule, f.line, f.severity, f.evidence)
                for f in structure.run(doc).findings
            ],
            [
                (
                    "table-column-count-undecided",
                    6,
                    "WARNING",
                    "lines 6-8 carry 3 table rows and no delimiter row, so this "
                    "run states no column count and `table-row-column-count` "
                    "decides nothing about them. The run opens `**M4**`",
                )
            ],
        )

    def test_a_table_that_carries_a_delimiter_row_is_decided_and_not_undecided(self):
        """The control for the rule above. A run that HAS a delimiter row is
        decided, so it must produce no undecided finding — otherwise the new
        rule would fire on every table in the document and say nothing."""
        doc = PlanDocument.from_text(
            "**AAA-1 · A task** — T0\n"
            "Files: `src/one.cpp`\n"
            "Depends: none\n"
            "Check: `ctest --test-dir build --no-tests=error -R t0_one`\n"
            "\n"
            "| # | What it is |\n"
            "|---|---|\n"
            "| **M4** | a row of a table that states its own column count |\n",
            name="inline",
        )

        self.assertEqual(structure.run(doc).findings, [])

    ASCII_ART = (
        "           |        |                    |\n"
        "           |        |        WAVE 3b   the internal join\n"
        "           |        |          REPO-9, SCH-19..SCH-30\n"
        "           |        |          usbhost USB-0..USB-4\n"
        "           |        |\n"
    )

    def art_doc(self, fenced):
        rail = "```\n" if fenced else ""
        return PlanDocument.from_text(
            "**AAA-1 · A task** — T0\n"
            "Files: `src/one.cpp`\n"
            "Depends: none\n"
            "Check: The wave diagram is drawn here:\n"
            f"{rail}{self.ASCII_ART}{rail}",
            name="inline",
        )

    def test_ascii_art_is_excluded_by_row_shape_and_not_only_by_the_fence(self):
        """Section 7.2's wave diagram, in the shape that produced a false
        measurement: pipes drawn as tree connectors, where a run of them has
        the shape of a delimiter row and the lines below it the shape of short
        rows. A scan that read this as a table called three of these lines
        broken rows.

        BOTH variants are asserted, and the un-fenced one is the load-bearing
        half. A row ends at a `|`, so a drawn line that ends in prose is not a
        row at all and the drawing never becomes a block — the fence is a
        second reason and not the only one. Asserting the fenced variant alone
        would leave the row shape free to be loosened with nothing going red,
        which is the edit that produced the false count.
        """
        self.assertEqual(structure.run(self.art_doc(fenced=True)).findings, [])
        self.assertEqual(structure.run(self.art_doc(fenced=False)).findings, [])


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
