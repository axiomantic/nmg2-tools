"""Tests for the report format and the no-input guard."""

import unittest

from planlint.finding import ERROR, WARNING, Finding, guard_no_input


class ReportTest(unittest.TestCase):
    def test_a_clean_result_names_what_it_examined(self):
        result = guard_no_input("graph", [], 207, "task blocks", "graph lint")

        self.assertEqual(result.report(), "graph: clean (207 task blocks examined)\n")
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


if __name__ == "__main__":
    unittest.main()
