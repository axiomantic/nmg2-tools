"""Tests for the symbol-closure lint.

The lint answers one question: when task A's work needs a symbol, a target, a
header or a build option that task B produces, is B inside A's transitive
dependency closure?

Real defects of this class reached the plan, and they were found by hand. The
`neg_hist_*` fixtures carry them in their PRE-REPAIR form, because the plan
holds them repaired and a clean run against the repaired plan is evidence of
nothing.
"""

import unittest

from tests.planlint.support import load_fixture

from planlint import closure
from planlint.document import PlanDocument


def run(name):
    return closure.run(load_fixture(name))


def rows(result):
    """`(rule, task, evidence)` for every finding, sorted."""
    return sorted((f.rule, f.task, f.evidence) for f in result.findings)


class ProducedSymbolsTest(unittest.TestCase):
    def test_a_targets_clause_and_an_exports_verb_both_produce(self):
        doc = load_fixture("neg_hist_brd0_target_link.md")

        produced = closure.produced_symbols(doc)

        self.assertEqual(sorted(produced["mcf5307::mcf5307"]), ["CPU-1"])
        self.assertEqual(sorted(produced["mcf5307"]), ["CPU-1"])
        self.assertEqual(sorted(produced["mcf5307_nim_objs"]), ["CPU-1"])

    def test_a_files_target_is_produced_by_the_task_that_declares_it(self):
        doc = load_fixture("neg_closure_header_and_candidate.md")

        self.assertEqual(sorted(closure.produced_symbols(doc)["alpha_lib"]), ["AAA-1"])

    def test_the_produced_target_set_is_the_files_clause_and_the_library_verbs(self):
        doc = load_fixture("neg_closure_header_and_candidate.md")

        self.assertEqual(closure.produced_targets(doc), {"alpha_lib"})

    def test_a_qualified_name_resolves_to_the_tasks_that_create_its_file(self):
        doc = load_fixture("neg_hist_repo9_type_name.md")

        self.assertEqual(
            sorted(closure.type_producers(doc, "Scheduler::Config")), ["SCH-17", "SCH-18"]
        )

    def test_a_qualified_name_with_no_matching_file_resolves_to_nothing(self):
        doc = load_fixture("neg_hist_repo9_type_name.md")

        self.assertEqual(closure.type_producers(doc, "Config::testOverride"), [])

    def test_a_header_resolves_to_every_task_whose_files_line_creates_it(self):
        doc = load_fixture("neg_closure_header_and_candidate.md")

        self.assertEqual(sorted(closure.header_producers(doc, "alpha.h")), ["AAA-1"])


class ConsumptionTest(unittest.TestCase):
    def test_a_link_sentence_yields_every_backticked_symbol_after_the_verb(self):
        doc = load_fixture("neg_hist_brd0_target_link.md")

        self.assertEqual(
            [(c.symbol, c.kind) for c in closure.consumptions(doc, doc.task("BRD-0"))],
            [
                ("hardwareLib", "symbol"),
                ("dsp56kEmu", "symbol"),
                ("synthLib", "symbol"),
                ("mcf5307::mcf5307", "symbol"),
            ],
        )

    def test_a_qualified_name_a_check_reads_is_a_consumption(self):
        doc = load_fixture("neg_hist_repo9_type_name.md")

        self.assertEqual(
            [(c.symbol, c.kind) for c in closure.consumptions(doc, doc.task("REPO-9"))],
            [("Scheduler::Config", "symbol"), ("Config::testOverride", "symbol")],
        )

    def test_an_include_is_a_consumption_of_its_header(self):
        doc = load_fixture("neg_closure_header_and_candidate.md")

        self.assertEqual(
            [(c.symbol, c.kind) for c in closure.consumptions(doc, doc.task("BBB-1"))],
            [("alpha.h", "header"), ("Alpha::Config", "symbol")],
        )

    def test_a_hedge_reaches_its_own_sentence_and_no_further(self):
        """`does not link` hedges the first sentence. The second sentence of the
        same line is a plain consumption, so a hedge cannot silence a line."""
        doc = load_fixture("neg_closure_header_and_candidate.md")

        self.assertEqual(
            [
                (c.symbol, c.hedged, c.hedge)
                for c in closure.consumptions(doc, doc.task("CCC-1"))
            ],
            [("alpha::alpha_lib", True, "does not"), ("hardwareLib", False, "")],
        )


class SentenceBoundaryTest(unittest.TestCase):
    """The defects the revert check found when the historical defects were put
    back into the REAL plan rather than into a fixture."""

    PLAN = (
        "**AAA-1 · The producer** — T0\n"
        "Files: `g2Lib/scheduler.h`\n"
        "Depends: none\n"
        "Check: The header declares `Scheduler::Config`.\n"
        "\n"
        "**BBB-1 · The reader** — T0\n"
        "Files: `g2Lib/test/t1_gate.cpp`\n"
        "Depends: none\n"
        "Check: **The wave moved for symbol availability rather than tidiness.** "
        "Its gate reads `Scheduler::Config`.\n"
    )

    def test_a_bold_marker_after_a_full_stop_still_closes_the_sentence(self):
        """`… rather than tidiness.** Its gate reads `X`` is TWO sentences. A
        splitter that wants whitespace straight after the stop reads it as one,
        and the hedge `rather than` then demotes a real violation to a
        candidate."""
        doc = PlanDocument.from_text(self.PLAN, name="inline")

        self.assertEqual(
            [(f.rule, f.severity) for f in closure.run(doc).findings],
            [("symbol-producer-unreachable", "ERROR")],
        )

    def test_compares_is_a_consumer_verb(self):
        """The real plan writes `compares the `Scheduler::Config` the golden
        render is constructed with`. A verb list without `compares` leaves that
        consumption with no verb, and a verb-less name is only a candidate."""
        doc = PlanDocument.from_text(
            self.PLAN.replace(
                "Its gate reads `Scheduler::Config`.",
                "The gate compares the `Scheduler::Config` the render carries.",
            ),
            name="inline",
        )

        self.assertEqual(
            [(f.rule, f.severity) for f in closure.run(doc).findings],
            [("symbol-producer-unreachable", "ERROR")],
        )


class HistoricalDefectTest(unittest.TestCase):
    """The evidence that this lint catches the historical defects."""

    def test_defect_1_the_link_on_a_target_cpu_1_exports_is_reported(self):
        self.assertEqual(
            rows(run("neg_hist_brd0_target_link.md")),
            [
                (
                    "target-producer-unreachable",
                    "BRD-0",
                    "BRD-0 names `mcf5307::mcf5307` (links); it is produced by CPU-1, "
                    "and BRD-0's dependency closure {BRD-0, REPO-12, REPO-3} holds "
                    "none of them",
                )
            ],
        )

    def test_defect_2_the_type_repo_9_reads_is_reported_with_every_producer(self):
        self.assertEqual(
            rows(run("neg_hist_repo9_type_name.md")),
            [
                (
                    "symbol-producer-unreachable",
                    "REPO-9",
                    "REPO-9 names `Scheduler::Config` (reads); it is produced by "
                    "SCH-17, SCH-18, and REPO-9's dependency closure "
                    "{BRD-0, REPO-12, REPO-8, REPO-9, SCH-0} holds none of them",
                )
            ],
        )

    def test_defect_3_the_gated_symbol_without_its_enabler_is_reported(self):
        self.assertEqual(
            rows(run("neg_hist_brd21_gated_link.md")),
            [
                (
                    "gated-symbol-without-enabler",
                    "BRD-21",
                    "BRD-21 names `mcf5307_exec` (forwards to); BRD-0 puts it behind "
                    "`option(G2_LINK_MCF5307 ... OFF)` in `source/nord/g2/g2Lib`, "
                    "BRD-23 turns the option ON, and BRD-21's dependency closure "
                    "{BRD-0, BRD-20, BRD-21, CPU-0, CPU-1} holds none of them",
                )
            ],
        )

    def test_the_task_that_declares_the_option_is_not_a_consumer_of_what_it_gates(self):
        """BRD-0 names `mcf5307::mcf5307` on the line that puts it behind the
        option. Declaring a gated link is the opposite of linking it, and a rule
        that reported the declarer would report every gated link in the plan."""
        self.assertEqual(
            [f.task for f in run("neg_hist_brd21_gated_link.md").findings], ["BRD-21"]
        )

    def test_defect_3_is_not_reported_as_a_missing_producer(self):
        """CPU-1 produces `mcf5307_exec` and CPU-1 IS reachable. The producer
        rule is silent here on purpose, and the option rule is what fires. A
        lint that reported the producer instead would have named the wrong
        repair."""
        self.assertEqual(
            [f.rule for f in run("neg_hist_brd21_gated_link.md").findings],
            ["gated-symbol-without-enabler"],
        )


class HeaderAndCandidateTest(unittest.TestCase):
    def test_an_include_of_an_unreachable_header_is_an_error(self):
        self.assertIn(
            (
                "header-producer-unreachable",
                "BBB-1",
                "BBB-1 includes `alpha.h`; it is created by AAA-1, and BBB-1's "
                "dependency closure {BBB-1} holds none of them",
            ),
            rows(run("neg_closure_header_and_candidate.md")),
        )

    def test_a_hedged_consumption_is_a_candidate_and_not_an_error(self):
        self.assertIn(
            (
                "symbol-closure-candidate",
                "CCC-1",
                'candidate — the sentence hedges with "does not"; CCC-1 names '
                "`alpha::alpha_lib` (link); it is produced by AAA-1, and CCC-1's "
                "dependency closure {CCC-1} holds none of them",
            ),
            rows(run("neg_closure_header_and_candidate.md")),
        )

    def test_the_candidate_carries_the_warning_severity_and_the_errors_do_not(self):
        result = run("neg_closure_header_and_candidate.md")

        self.assertEqual(
            sorted((f.rule, f.severity) for f in result.findings),
            [
                ("header-producer-unreachable", "ERROR"),
                ("symbol-closure-candidate", "WARNING"),
                ("symbol-producer-unreachable", "ERROR"),
            ],
        )

    def test_a_symbol_no_task_produces_is_never_reported(self):
        """`hardwareLib` is a name from the upstream fork. The lint knows no
        producer for it, and a lint that reported every unknown name would
        report the whole upstream surface."""
        result = run("neg_closure_header_and_candidate.md")

        # The fixture must still report something, or the filter below is empty
        # for the wrong reason and the assertion proves nothing.
        self.assertEqual(len(result.findings), 3)
        self.assertEqual(
            [f for f in result.findings if "hardwareLib" in f.evidence], []
        )

    def test_the_control_task_that_declares_the_producer_is_not_reported(self):
        result = run("neg_closure_header_and_candidate.md")

        self.assertEqual(len(result.findings), 3)
        self.assertEqual([f for f in result.findings if f.task == "DDD-1"], [])


class CleanPlanTest(unittest.TestCase):
    def test_the_clean_plan_reports_nothing(self):
        result = run("clean_plan.md")

        self.assertEqual(result.findings, [])

    def test_the_clean_plan_examines_the_consumptions_it_carries(self):
        result = run("clean_plan.md")

        # CCC-2 names `gamma::gamma_lib`, which it produces itself. EEE-1 carries
        # the header, the target and the type, and reaches CCC-2 for all three.
        self.assertEqual(
            (result.examined, result.examined_label),
            (4, "consumptions"),
        )

    def test_a_task_never_consumes_from_itself(self):
        doc = load_fixture("clean_plan.md")
        task = next(t for t in doc.tasks if t.ident == "CCC-2")

        # The precondition, pinned. CCC-2 produces `gamma::gamma_lib` and names
        # it again in its own body. Without these two assertions the assertion
        # below passes on an empty finding list, and thus proves nothing.
        self.assertEqual(sorted(closure.produced_symbols(doc)["gamma::gamma_lib"]), ["CCC-2"])
        self.assertIn(
            "gamma::gamma_lib", [c.symbol for c in closure.consumptions(doc, task)]
        )

        self.assertEqual(
            [f for f in closure.run(doc).findings if f.task == "CCC-2"], []
        )


class NoInputTest(unittest.TestCase):
    def test_a_document_with_no_consumption_is_a_hard_error(self):
        result = closure.run(
            PlanDocument.from_text(
                "**AAA-1 · A task** — T0\n"
                "Files: `src/one.cpp`\n"
                "Depends: none\n"
                "Check: The operator confirms it.\n",
                name="inline",
            )
        )

        self.assertEqual(
            [(f.rule, f.message) for f in result.findings],
            [("no-input", "the closure lint examined 0 consumptions")],
        )


if __name__ == "__main__":
    unittest.main()
