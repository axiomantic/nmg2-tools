"""Tests for the report format and the no-input guard."""

import unittest

from planlint.finding import (
    ERROR,
    INFO,
    WARNING,
    Finding,
    LintResult,
    guard_no_input,
)


class ReportTest(unittest.TestCase):
    def test_a_clean_result_names_what_it_examined(self):
        result = guard_no_input("graph", [], 207, "task blocks", "graph lint")

        self.assertEqual(result.report(), "graph: clean (207 task blocks examined)\n")
        self.assertFalse(result.failed)

    def test_a_notice_is_printed_under_a_clean_result(self):
        """A clean run is where a coverage notice matters most: a report
        silent about what a lint decides reads exactly like one in which the
        lint decided everything."""
        result = guard_no_input(
            "secondwrite", [], 242, "task bodies", "second-write lint",
            notice="COVERAGE: 4 of 5 tests decided.",
        )

        self.assertEqual(
            result.report(),
            "secondwrite: clean (242 task bodies examined)\n"
            "  COVERAGE: 4 of 5 tests decided.\n",
        )
        self.assertFalse(result.failed)

    def test_a_notice_is_printed_under_a_report_that_carries_findings(self):
        result = guard_no_input(
            "secondwrite",
            [Finding(rule="r", message="m")],
            242, "task bodies", "second-write lint",
            notice="COVERAGE: 4 of 5 tests decided.",
        )

        self.assertEqual(
            result.report(),
            "secondwrite: 1 finding(s) (242 task bodies examined)\n"
            "  [ERROR] r\n"
            "      m\n"
            "  COVERAGE: 4 of 5 tests decided.\n",
        )
        self.assertTrue(result.failed)

    def test_a_notice_does_not_reach_the_verdict(self):
        """A notice changes the report's WORDING and never its exit code.
        Scoring it would change what `if planlint; then` means for every
        existing caller, which is a separate decision from making a gap
        visible."""
        result = guard_no_input(
            "secondwrite", [], 242, "task bodies", "second-write lint",
            notice="COVERAGE: 4 of 5 tests decided.",
        )

        self.assertFalse(result.failed)

    def test_a_finding_with_a_line_prints_the_line(self):
        result = guard_no_input(
            "graph",
            [Finding(rule="r", message="m", task="AAA-1", section="9. Tasks",
                     line=42, evidence="e")],
            1, "task blocks", "graph lint",
        )

        self.assertEqual(
            result.report(),
            "graph: 1 finding(s) (1 task blocks examined)\n"
            "  [ERROR] r  AAA-1  line 42\n"
            "      section: 9. Tasks\n"
            "      m\n"
            "      evidence: e\n",
        )

    def test_a_finding_with_no_line_and_no_task_prints_neither(self):
        result = guard_no_input(
            "payload",
            [Finding(rule="r", message="m", section="7.8", evidence="e")],
            1, "committed files", "payload lint",
        )

        self.assertEqual(
            result.report(),
            "payload: 1 finding(s) (1 committed files examined)\n"
            "  [ERROR] r\n"
            "      section: 7.8\n"
            "      m\n"
            "      evidence: e\n",
        )

    def test_no_input_is_a_hard_error_even_with_no_other_finding(self):
        result = guard_no_input("counts", [], 0, "stated counts", "counts lint")

        self.assertEqual(
            [(f.rule, f.message, f.severity) for f in result.findings],
            [("no-input", "the counts lint examined 0 stated counts", ERROR)],
        )
        self.assertTrue(result.failed)

    def test_a_warning_alone_still_fails_the_run(self):
        result = guard_no_input(
            "checks",
            [Finding(rule="r", message="m", severity=WARNING)],
            1, "commands", "check lint",
        )

        self.assertTrue(result.failed)


class CollapsedReportTest(unittest.TestCase):
    """`report(full=False)`: every ERROR in full, one line per lower-severity
    rule with its count, and the flag that prints the rest."""

    def result(self, findings):
        return LintResult(
            name="checks",
            findings=findings,
            examined=300,
            examined_label="Check: blocks",
        )

    def test_full_is_the_default_so_no_existing_caller_changes(self):
        """`freshness` renders the same class and never asked for a collapse.
        The default is the report every existing caller already gets."""
        result = self.result([Finding(rule="r", message="m", severity=WARNING)])

        self.assertEqual(result.report(), result.report(full=True))
        self.assertIn("      m\n", result.report())

    def test_the_collapse_prints_the_error_in_full_and_the_warning_as_a_count(self):
        result = self.result(
            [
                Finding(rule="e", message="em", task="DSP-7", line=12),
                Finding(rule="w", message="wm", task="T-1", severity=WARNING),
                Finding(rule="w", message="wm", task="T-2", severity=WARNING),
            ]
        )

        self.assertEqual(
            result.report(full=False),
            "checks: 3 finding(s) (300 Check: blocks examined)\n"
            "  [ERROR] e  DSP-7  line 12\n"
            "      em\n"
            "  collapsed to one line per rule; --full-warnings prints every one:\n"
            "    [WARNING] w  2\n",
        )

    def test_two_findings_alike_in_every_field_are_counted_twice(self):
        """`Finding` is a frozen dataclass, so two findings that differ in no
        field are EQUAL. A collapse that partitioned by identity against a
        list would drop one of a duplicated pair and under-count in silence."""
        twin = Finding(rule="w", message="m", severity=WARNING)
        result = self.result([twin, twin])

        self.assertEqual(result.collapsed_counts(), [(WARNING, "w", 2)])

    def test_a_severity_below_warning_collapses_under_its_own_severity(self):
        """The collapse is `severity != ERROR` and not `severity == WARNING`,
        so a rule that starts emitting INFO does not silently print in full."""
        result = self.result(
            [
                Finding(rule="w", message="m", severity=WARNING),
                Finding(rule="i", message="m", severity=INFO),
                Finding(rule="i", message="m", severity=INFO),
            ]
        )

        self.assertEqual(
            result.collapsed_counts(), [(WARNING, "w", 1), (INFO, "i", 2)]
        )
        self.assertIn("    [INFO] i  2\n", result.report(full=False))

    def test_the_collapse_never_reaches_the_verdict(self):
        """Collapsing changes the report's WORDING and never `failed`."""
        result = self.result([Finding(rule="w", message="m", severity=WARNING)])
        result.report(full=False)

        self.assertTrue(result.failed)

    def test_a_notice_is_still_printed_under_a_collapsed_report(self):
        """A coverage notice says which checks a lint DECIDED. Losing it under
        the collapse would trade one silence for another."""
        result = LintResult(
            name="secondwrite",
            findings=[Finding(rule="w", message="m", severity=WARNING)],
            examined=242,
            examined_label="task bodies",
            notice="COVERAGE: 4 of 5 tests decided.",
        )

        self.assertTrue(result.report(full=False).endswith(
            "  COVERAGE: 4 of 5 tests decided.\n"
        ))

    def test_a_clean_result_reads_the_same_in_both_modes(self):
        result = guard_no_input("graph", [], 207, "task blocks", "graph lint")

        self.assertEqual(result.report(full=False), result.report(full=True))

    def test_a_result_with_only_errors_reads_the_same_in_both_modes(self):
        """Nothing to collapse means no collapse line. A report that announced
        a collapse of nothing would be furniture."""
        result = self.result([Finding(rule="e", message="m")])

        self.assertEqual(result.report(full=False), result.report(full=True))


if __name__ == "__main__":
    unittest.main()
