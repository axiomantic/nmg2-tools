"""Tests for the dependency-graph lint (section 7.6 assertions 2 and 3)."""

import unittest

from tests.planlint.support import load_fixture, rules

from planlint import graph
from planlint.document import PlanDocument


def run(name):
    return graph.run(load_fixture(name))


class DependsParseTest(unittest.TestCase):
    def test_none_declares_no_edge(self):
        edges, findings = graph.parse_depends("none")

        self.assertEqual((edges, findings), ([], []))

    def test_a_comma_list_declares_one_edge_for_each_item(self):
        edges, findings = graph.parse_depends("REPO-1, REPO-2, BRD-0")

        self.assertEqual(edges, ["REPO-1", "REPO-2", "BRD-0"])
        self.assertEqual(findings, [])

    def test_a_range_expands(self):
        edges, findings = graph.parse_depends("BRD-1 to BRD-4, CPU-0")

        self.assertEqual(edges, ["BRD-1", "BRD-2", "BRD-3", "BRD-4", "CPU-0"])
        self.assertEqual(findings, [])

    def test_bold_markers_around_an_item_do_not_change_it(self):
        edges, findings = graph.parse_depends("SCH-12, **SCH-18**, **SCH-19**, BRD-21")

        self.assertEqual(edges, ["SCH-12", "SCH-18", "SCH-19", "BRD-21"])
        self.assertEqual(findings, [])

    def test_a_qualifier_after_an_item_keeps_the_edge_and_reports_nothing(self):
        edges, findings = graph.parse_depends(
            "REPO-2, TOOL-12, **REPO-15 for the T1 half only**"
        )

        self.assertEqual(edges, ["REPO-2", "TOOL-12", "REPO-15"])
        self.assertEqual(findings, [])

    def test_a_marker_sentence_declares_no_edge_and_reports_no_defect(self):
        edges, findings = graph.parse_depends("BRD-7, TOOL-5, BRD-21. **PENDING SPK-10.**")

        self.assertEqual(edges, ["BRD-7", "TOOL-5", "BRD-21"])
        self.assertEqual(findings, [])

    def test_a_scheduling_note_declares_no_edge_and_is_reported(self):
        edges, findings = graph.parse_depends("AAA-1. Scheduled before BBB-1.")

        self.assertEqual(edges, ["AAA-1"])
        self.assertEqual(
            [(f.rule, f.evidence) for f in findings],
            [("depends-prose", "Scheduled before BBB-1. → BBB-1")],
        )

    def test_an_identifier_inside_a_clause_declares_no_edge_and_is_reported(self):
        edges, findings = graph.parse_depends(
            "AAA-1, and it is also scheduled after BBB-1 runs"
        )

        self.assertEqual(edges, ["AAA-1"])
        self.assertEqual(
            [(f.rule, f.evidence) for f in findings],
            [("depends-prose", "and it is also scheduled after BBB-1 runs → BBB-1")],
        )

    def test_a_prose_clause_naming_no_task_is_reported_as_depends_prose(self):
        edges, findings = graph.parse_depends(
            "**REPO-15**, which produces the corpus this repository carries. "
            "**Not on the critical path to M2.** Schedule it before M3."
        )

        self.assertEqual(edges, ["REPO-15"])
        self.assertEqual(
            [f.rule for f in findings],
            ["depends-prose", "depends-prose", "depends-prose"],
        )

    def test_zero_identifier_prose_item_is_flagged(self):
        edges, findings = graph.parse_depends("whatever finishes first")

        self.assertEqual(edges, [])
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].rule, "depends-prose")
        self.assertEqual(findings[0].evidence, "whatever finishes first")

    def test_item_combining_valid_identifier_and_zero_identifier_prose(self):
        edges, findings = graph.parse_depends("CPU-1, whatever finishes first")

        self.assertEqual(edges, ["CPU-1"])
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].rule, "depends-prose")
        self.assertEqual(findings[0].evidence, "whatever finishes first")


class GraphLintTest(unittest.TestCase):
    def test_the_clean_plan_reports_nothing(self):
        result = run("clean_plan.md")

        self.assertEqual(result.findings, [])
        self.assertEqual(result.examined, 8)

    def test_a_two_task_cycle_is_reported_with_both_members(self):
        result = run("neg_graph_cycle.md")

        self.assertEqual(rules(result.findings), ["dependency-cycle"])
        self.assertEqual(
            [(f.task, f.evidence) for f in result.findings],
            [("AAA-1", "strongly connected component: AAA-1, AAA-2")],
        )

    def test_a_self_loop_is_reported(self):
        result = run("neg_graph_self_loop.md")

        self.assertEqual(
            [(f.rule, f.task, f.evidence) for f in result.findings],
            [("self-loop", "AAA-2", "Depends: AAA-1, AAA-2")],
        )

    def test_an_unknown_identifier_is_reported_once_for_each_name(self):
        result = run("neg_graph_unknown_dep.md")

        self.assertEqual(
            [(f.rule, f.task, f.evidence) for f in result.findings],
            [
                ("unknown-dependency", "AAA-2", "Depends: ZZZ-9 → ZZZ-9"),
                ("unknown-dependency", "BBB-1", "Depends: AAA-1 to AAA-4 → AAA-3"),
                ("unknown-dependency", "BBB-1", "Depends: AAA-1 to AAA-4 → AAA-4"),
            ],
        )

    def test_prose_on_a_depends_line_is_reported_and_makes_no_false_cycle(self):
        result = run("neg_graph_prose_depends.md")

        self.assertEqual(
            [(f.rule, f.task, f.evidence) for f in result.findings],
            [
                ("depends-prose", "AAA-2", "Scheduled before BBB-1. → BBB-1"),
                (
                    "depends-prose",
                    "AAA-3",
                    "and it is also scheduled after BBB-1 runs → BBB-1",
                ),
            ],
        )

    def test_a_document_with_no_task_block_is_a_hard_error(self):
        result = graph.run(PlanDocument.from_text("# Nothing here\n", name="inline"))

        self.assertEqual(
            [(f.rule, f.message) for f in result.findings],
            [("no-input", "the graph lint examined 0 task blocks")],
        )
        self.assertEqual(result.examined, 0)


if __name__ == "__main__":
    unittest.main()
