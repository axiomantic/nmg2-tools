"""Tests for the completion-gate lint (section 24.6 row W3-422)."""

import unittest

from tests.planlint.support import load_fixture

from planlint import gate
from planlint.document import PlanDocument


def run(name):
    return gate.run(load_fixture(name))


def reported(result):
    return sorted(
        (f.rule, f.task, f.severity, f.evidence) for f in result.findings
    )


class CalibratedPairTest(unittest.TestCase):
    """The two fixtures differ by two `~~` pairs on one line. One is silent and
    the other reports, so what the lint reads is the strike and not the text
    around it."""

    def test_a_dependency_that_carries_a_live_marker_is_silent(self):
        result = run("pos_gate_complete.md")

        self.assertEqual(result.findings, [])
        self.assertEqual(result.examined, 2)
        self.assertEqual(result.examined_label, "task bodies")

    def test_a_dependency_whose_marker_is_struck_is_reported(self):
        result = run("neg_gate_incomplete.md")

        self.assertEqual(
            reported(result),
            [
                (
                    "done-marker-over-incomplete-dependency",
                    "AAA-2",
                    "ERROR",
                    "AAA-2 carries a completion marker at line 27; AAA-1 is on "
                    "its `Depends:` line and carries none",
                )
            ],
        )

    def test_the_clean_plan_reports_nothing(self):
        result = run("clean_plan.md")

        self.assertEqual(result.findings, [])
        self.assertEqual(result.examined, 8)


class DispositionTest(unittest.TestCase):
    """Which rule a pair earns is decided by the DEPENDENCY's own declared tier
    substitute, so a new pair is classified by what its dependency says about
    itself and never by an exception list amended once per case."""

    def test_every_pair_of_the_disposition_fixture_is_accounted_for(self):
        self.assertEqual(
            reported(run("neg_gate_dispositions.md")),
            [
                (
                    "done-marker-over-a-dependency-this-plan-does-not-schedule",
                    "BBB-1",
                    "WARNING",
                    "BBB-1 carries a completion marker at line 45; OPR-1 is on "
                    "its `Depends:` line and carries none. OPR-1 is declared "
                    "OPERATOR: the task needs an outward action only the "
                    "operator may take",
                ),
                (
                    "done-marker-over-a-dependency-this-plan-does-not-schedule",
                    "DDD-1",
                    "WARNING",
                    "DDD-1 carries a completion marker at line 59; DEF-1 is on "
                    "its `Depends:` line and carries none. DEF-1 is declared "
                    "deferred: the task is listed and not scheduled, and has "
                    "no check to run",
                ),
                (
                    "done-marker-over-a-dependency-this-plan-does-not-schedule",
                    "EEE-1",
                    "WARNING",
                    "EEE-1 carries a completion marker at line 66; UPS-1 is on "
                    "its `Depends:` line and carries none. UPS-1 is declared "
                    "upstream: the check is a pull request against a "
                    "repository this project does not own",
                ),
                (
                    "done-marker-over-incomplete-dependency",
                    "CCC-1",
                    "ERROR",
                    "CCC-1 carries a completion marker at line 52; SPK-1 is on "
                    "its `Depends:` line and carries none",
                ),
                (
                    "done-marker-over-incomplete-dependency",
                    "FFF-2",
                    "ERROR",
                    "FFF-2 carries a completion marker at line 79; FFF-3 is on "
                    "its `Depends:` line and carries none",
                ),
            ],
        )

    def test_a_spike_dependency_is_project_work_and_earns_the_error_rule(self):
        """§1.5 gives THROWAWAY a check the operator runs against `extracted/`.
        It is work this plan schedules, so excusing it would silence the three
        pairs row W3-422 names as its proof."""
        self.assertEqual(
            [
                (f.rule, f.severity)
                for f in run("neg_gate_dispositions.md").findings
                if f.task == "CCC-1"
            ],
            [("done-marker-over-incomplete-dependency", "ERROR")],
        )

    def test_the_chain_reports_the_edge_above_the_gap_and_not_the_head(self):
        """FFF-1 → FFF-2 → FFF-3 with FFF-3 unmarked. Reporting FFF-1 → FFF-3
        as well would add a second line a reader repairs the same way."""
        self.assertEqual(
            sorted(
                (f.task, f.evidence.split(";")[1].split()[0])
                for f in run("neg_gate_dispositions.md").findings
                if f.task.startswith("FFF-")
            ),
            [("FFF-2", "FFF-3")],
        )


class NoInputTest(unittest.TestCase):
    def test_a_document_with_no_task_block_is_a_hard_error(self):
        result = gate.run(PlanDocument.from_text("# A plan with no task\n", name="inline"))

        self.assertEqual(
            [(f.rule, f.task, f.severity) for f in result.findings],
            [("no-input", "", "ERROR")],
        )
        self.assertEqual(result.examined, 0)


if __name__ == "__main__":
    unittest.main()
