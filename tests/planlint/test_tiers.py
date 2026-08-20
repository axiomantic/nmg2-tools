"""Tests for the tier-purity lint (sections 1.3 rule 8, 5.2 and 7.6 assertions 1, 4, 6)."""

import unittest

from tests.planlint.support import load_fixture

from planlint import tiers
from planlint.document import PlanDocument


def run(name):
    return tiers.run(load_fixture(name))


def pairs(result):
    return sorted((f.rule, f.task) for f in result.findings)


def triples(result):
    return sorted((f.rule, f.task, f.evidence) for f in result.findings)


REPOSITORIES = """### 3.1 Layout B

| Repository | Visibility |
|---|---|
| `axiomantic/artifacts` | **PRIVATE** |
| `axiomantic/core` | PUBLIC |

"""


def admissibility_doc(register_rows, tasks):
    """A document carrying section 3.1's table, section 7.8's register and tasks."""
    body = REPOSITORIES + "### 7.8 The recorded-fixture register\n\n"
    body += "| Fixture | Path | Named by | Repository | Visibility |\n|---|---|---|---|---|\n"
    body += "".join(register_rows)
    body += "\n## 9. The tasks\n\n" + tasks
    return PlanDocument.from_text(body, name="inline")


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
                ("t0-gated-check", "AAA-3"),
                ("t0-reads-private-fixture", "AAA-4"),
            ],
        )

    def test_a_t0_task_that_depends_on_a_t1_task_names_the_edge_and_the_conjunct(self):
        result = run("neg_tier_purity.md")

        self.assertIn(
            (
                "t0-depends-t1",
                "AAA-2",
                "AAA-2 is T0; it depends on BBB-1, which is T1. Conjunct (b) fails: "
                "the check names `derived/table.json`, which BBB-1 produces and the "
                "section 7.8 register places in `artifacts`, a repository section "
                "3.1's table marks PRIVATE.",
            ),
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

    def test_a_range_that_satisfies_the_conjuncts_is_a_range_defect_and_not_a_tier_defect(self):
        result = run("neg_tier_purity.md")

        self.assertEqual(
            sorted(f.rule for f in result.findings if f.task == "BBB-2"),
            ["range-holds-conditional", "range-holds-higher-tier"],
        )

    def test_a_document_with_no_task_block_is_a_hard_error(self):
        result = tiers.run(PlanDocument.from_text("# Nothing\n", name="inline"))

        self.assertEqual(
            [(f.rule, f.message) for f in result.findings],
            [("no-input", "the tier lint examined 0 task blocks")],
        )


PUBLIC_ROW = "| The coverage file | `module_map.coverage` | BBB-1 | `core` | PUBLIC |\n"
PRIVATE_REPO_ROW = "| The derived table | `derived/table.json` | BBB-1 | `artifacts` | PUBLIC |\n"
PRIVATE_ROW = "| The recorded trace | `fixtures/protocol/` | BBB-1 | `artifacts` | **PRIVATE** |\n"

PRODUCER = """**BBB-1 · The gated producer** — T1
Files: `tests/t1_beta.cpp`, `module_map.coverage`, `derived/table.json`, `g2Lib/board.h`
Depends: none
Check: `ctest --test-dir build --no-tests=error -R t1_beta` with `NMG2_ARTIFACTS` set.
"""

MIDDLE = """**AAA-2 · The middle** — T0
Files: `tests/t0_gamma.cpp`
Depends: BBB-1
Check: `ctest --test-dir build --no-tests=error -R t0_gamma`.

"""


def reader(depends, check):
    return (
        "**AAA-1 · The reader** — T0\n"
        "Files: `tests/t0_alpha.cpp`\n"
        f"Depends: {depends}\n"
        f"Check: {check}\n\n"
    )


class AdmissibilityPredicateTest(unittest.TestCase):
    """Section 5.2 rule 7: a T0-to-higher-tier edge is admissible exactly when
    the T0 check returns the same verdict on a machine that never held the
    artifact."""

    def test_a_production_edge_reading_a_public_committed_path_is_admitted(self):
        doc = admissibility_doc(
            [PUBLIC_ROW],
            reader(
                "BBB-1",
                "`ctest --test-dir build --no-tests=error -R t0_alpha`. It reads "
                "`module_map.coverage` out of the committed tree.",
            )
            + PRODUCER,
        )

        self.assertEqual(tiers.run(doc).findings, [])

    def test_an_edge_whose_check_reads_a_path_in_a_private_repository_fails_conjunct_b(self):
        doc = admissibility_doc(
            [PRIVATE_REPO_ROW],
            reader(
                "BBB-1",
                "`ctest --test-dir build --no-tests=error -R t0_alpha`. It reads "
                "`derived/table.json` out of the committed tree.",
            )
            + PRODUCER,
        )

        self.assertEqual(
            triples(tiers.run(doc)),
            [
                (
                    "t0-depends-t1",
                    "AAA-1",
                    "AAA-1 is T0; it depends on BBB-1, which is T1. Conjunct (b) "
                    "fails: the check names `derived/table.json`, which BBB-1 "
                    "produces and the section 7.8 register places in `artifacts`, a "
                    "repository section 3.1's table marks PRIVATE.",
                )
            ],
        )

    def test_an_edge_whose_check_is_gated_on_the_artifact_fails_conjunct_a(self):
        doc = admissibility_doc(
            [PUBLIC_ROW],
            reader(
                "BBB-1",
                "`ctest --test-dir build --no-tests=error -R t0_alpha` with "
                "`NMG2_ARTIFACTS` set. It reads `module_map.coverage` out of the "
                "committed tree.",
            )
            + PRODUCER,
        )

        self.assertEqual(
            triples(tiers.run(doc)),
            [
                (
                    "t0-depends-t1",
                    "AAA-1",
                    "AAA-1 is T0; it depends on BBB-1, which is T1. Conjunct (a) "
                    "fails: the check is conditioned on the artifact — `ctest "
                    "--test-dir build --no-tests=error -R t0_alpha` with "
                    "`NMG2_ARTIFACTS` set.",
                ),
                (
                    "t0-gated-check",
                    "AAA-1",
                    "`ctest --test-dir build --no-tests=error -R t0_alpha` with "
                    "`NMG2_ARTIFACTS` set",
                ),
            ],
        )

    def test_an_edge_whose_check_names_a_private_fixture_fails_both_decided_conjuncts(self):
        doc = admissibility_doc(
            [PRIVATE_ROW],
            reader(
                "BBB-1",
                "`ctest --test-dir build --no-tests=error -R t0_alpha`. It reads "
                "`fixtures/protocol/` out of the recorded corpus.",
            )
            + PRODUCER,
        )

        self.assertEqual(
            triples(tiers.run(doc)),
            [
                (
                    "t0-depends-t1",
                    "AAA-1",
                    "AAA-1 is T0; it depends on BBB-1, which is T1. Conjunct (a) "
                    "fails: the check names `fixtures/protocol/`, which the section "
                    "7.8 register marks PRIVATE. Conjunct (b) fails: the check names "
                    "`fixtures/protocol/`, which BBB-1 produces and the section 7.8 "
                    "register places in `artifacts`, a repository section 3.1's table "
                    "marks PRIVATE.",
                ),
                (
                    "t0-reads-private-fixture",
                    "AAA-1",
                    "reads `fixtures/protocol/`, which the section 7.8 register marks "
                    "PRIVATE (named by BBB-1)",
                ),
            ],
        )

    def test_a_higher_tier_task_reached_only_through_a_t0_task_is_judged_and_the_route_is_named(self):
        doc = admissibility_doc(
            [PRIVATE_REPO_ROW],
            reader(
                "AAA-2",
                "`ctest --test-dir build --no-tests=error -R t0_alpha`. It reads "
                "`derived/table.json` out of the committed tree.",
            )
            + MIDDLE
            + PRODUCER,
        )

        self.assertEqual(
            triples(tiers.run(doc)),
            [
                (
                    "t0-depends-t1",
                    "AAA-1",
                    "AAA-1 is T0; it reaches BBB-1 through AAA-2, and BBB-1 is T1. "
                    "Conjunct (b) fails: the check names `derived/table.json`, which "
                    "BBB-1 produces and the section 7.8 register places in "
                    "`artifacts`, a repository section 3.1's table marks PRIVATE.",
                )
            ],
        )

    def test_a_higher_tier_task_reached_through_a_t0_task_is_admitted_when_the_conjuncts_hold(self):
        doc = admissibility_doc(
            [PUBLIC_ROW],
            reader(
                "AAA-2",
                "`ctest --test-dir build --no-tests=error -R t0_alpha`. It reads "
                "`module_map.coverage` out of the committed tree.",
            )
            + MIDDLE
            + PRODUCER,
        )

        self.assertEqual(tiers.run(doc).findings, [])

    def test_a_path_the_register_does_not_carry_is_not_decided_and_the_edge_is_admitted(self):
        doc = admissibility_doc(
            [PUBLIC_ROW],
            reader(
                "BBB-1",
                "`ctest --test-dir build --no-tests=error -R t0_alpha`. It reads "
                "`g2Lib/board.h` out of the committed tree.",
            )
            + PRODUCER,
        )

        self.assertEqual(tiers.run(doc).findings, [])


if __name__ == "__main__":
    unittest.main()
