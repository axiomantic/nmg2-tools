"""Tests for the wave-ordering lint (section 7.6 assertion 5)."""

import unittest

from tests.planlint.support import load_fixture

from planlint import waves
from planlint.document import PlanDocument


def run(name):
    return waves.run(load_fixture(name))


class WaveLintTest(unittest.TestCase):
    def test_the_clean_plan_reports_nothing(self):
        result = run("clean_plan.md")

        self.assertEqual(result.findings, [])
        self.assertEqual(result.examined, 8)

    def test_a_task_that_precedes_its_dependency_is_reported(self):
        result = run("neg_wave_order.md")

        self.assertIn(
            (
                "wave-order",
                "AAA-2",
                "AAA-2 is wave 1 (order 1); it depends on AAA-1, which is wave 3a (order 3)",
            ),
            [(f.rule, f.task, f.evidence) for f in result.findings],
        )

    def test_a_task_the_wave_table_names_nowhere_is_reported(self):
        result = run("neg_wave_order.md")

        self.assertIn(
            ("task-without-wave", "BBB-1", "the section 7.2 wave table names BBB-1 in no row"),
            [(f.rule, f.task, f.evidence) for f in result.findings],
        )

    def test_a_wave_entry_with_no_task_block_is_reported(self):
        result = run("neg_wave_order.md")

        self.assertIn(
            ("wave-without-task", "CCC-9", "wave 3a names CCC-9; no task block defines it"),
            [(f.rule, f.task, f.evidence) for f in result.findings],
        )

    def test_every_finding_of_the_negative_fixture_is_accounted_for(self):
        result = run("neg_wave_order.md")

        self.assertEqual(
            sorted((f.rule, f.task) for f in result.findings),
            [
                ("task-without-wave", "BBB-1"),
                ("wave-order", "AAA-2"),
                ("wave-without-task", "CCC-9"),
            ],
        )

    def test_a_document_with_no_wave_table_is_a_hard_error(self):
        result = waves.run(
            PlanDocument.from_text(
                "**AAA-1 · A task** — T0\nDepends: none\nCheck: `ctest`\n", name="inline"
            )
        )

        self.assertEqual(
            [(f.rule, f.task) for f in result.findings],
            [("task-without-wave", "AAA-1"), ("no-input", "")],
        )
        self.assertEqual(result.examined, 0)


if __name__ == "__main__":
    unittest.main()
