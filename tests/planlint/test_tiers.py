"""Tests for the tier-purity lint (sections 1.3 rule 8, 5.2 and 7.6 assertions 1, 4, 6)."""

import unittest

from tests.planlint.support import load_fixture

from planlint import tiers
from planlint.document import PlanDocument


def run(name):
    return tiers.run(load_fixture(name))


def pairs(result):
    return sorted((f.rule, f.task) for f in result.findings)


class TierLintTest(unittest.TestCase):
    def test_the_clean_plan_reports_nothing(self):
        result = run("clean_plan.md")

        self.assertEqual(result.findings, [])
        self.assertEqual(result.examined, 8)

    def test_every_defect_of_the_negative_fixture_is_reported_and_nothing_else(self):
        result = run("neg_tier_purity.md")

        self.assertEqual(
            pairs(result),
            [
                ("missing-tier", "AAA-5"),
                ("range-holds-conditional", "BBB-2"),
                ("range-holds-higher-tier", "BBB-2"),
                ("t0-depends-t1", "AAA-2"),
                ("t0-depends-t1", "BBB-2"),
                ("t0-gated-check", "AAA-3"),
                ("t0-reads-private-fixture", "AAA-4"),
            ],
        )

    def test_a_t0_task_that_depends_on_a_t1_task_names_the_edge(self):
        result = run("neg_tier_purity.md")

        self.assertIn(
            ("t0-depends-t1", "AAA-2", "AAA-2 is T0; it depends on BBB-1, which is T1"),
            [(f.rule, f.task, f.evidence) for f in result.findings],
        )

    def test_a_t0_check_gated_on_the_artifact_variable_names_the_phrase(self):
        result = run("neg_tier_purity.md")

        self.assertIn(
            (
                "t0-gated-check",
                "AAA-3",
                "`ctest --test-dir build --no-tests=error -R t0_gamma` with "
                "`NMG2_ARTIFACTS` set",
            ),
            [(f.rule, f.task, f.evidence) for f in result.findings],
        )

    def test_a_t0_check_that_reads_a_private_fixture_names_the_register_row(self):
        result = run("neg_tier_purity.md")

        self.assertIn(
            (
                "t0-reads-private-fixture",
                "AAA-4",
                "reads `fixtures/protocol/`, which the section 7.8 register marks "
                "PRIVATE (named by BBB-1)",
            ),
            [(f.rule, f.task, f.evidence) for f in result.findings],
        )

    def test_a_range_that_swallows_a_higher_tier_and_a_conditional_names_both(self):
        result = run("neg_tier_purity.md")

        found = {f.rule: f.evidence for f in result.findings if f.task == "BBB-2"}
        self.assertEqual(
            found["range-holds-higher-tier"],
            "the range `BBB-1 to BBB-3` holds BBB-1, which is T1; BBB-2 is T0",
        )
        self.assertEqual(
            found["range-holds-conditional"],
            "the range `BBB-1 to BBB-3` holds BBB-3, which section 24.4 marks conditional",
        )

    def test_a_header_line_with_no_tier_field_is_reported(self):
        result = run("neg_tier_purity.md")

        self.assertIn(
            ("missing-tier", "AAA-5", "**AAA-5 · The untiered**"),
            [(f.rule, f.task, f.evidence) for f in result.findings],
        )

    def test_a_stated_non_tier_disposition_is_not_a_missing_tier(self):
        doc = PlanDocument.from_text(
            "**SPK-0 · The spike workspace** — no tier (THROWAWAY)\n"
            "Files: `spike/README.md`\n"
            "Depends: none\n"
            "Check: The workspace exists and the report names each criterion.\n"
            "\n"
            "**OP-1 · An operator action** — OPERATOR\n"
            "Files: `docs/op.md`\n"
            "Depends: none\n"
            "Check: The operator confirms the action and records it.\n",
            name="inline",
        )

        self.assertEqual(tiers.run(doc).findings, [])

    def test_a_document_with_no_task_block_is_a_hard_error(self):
        result = tiers.run(PlanDocument.from_text("# Nothing\n", name="inline"))

        self.assertEqual(
            [(f.rule, f.message) for f in result.findings],
            [("no-input", "the tier lint examined 0 task blocks")],
        )


if __name__ == "__main__":
    unittest.main()
