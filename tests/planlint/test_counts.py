"""Tests for the self-consistency lint: every count the plan states about
itself must match its own rows."""

import unittest

from tests.planlint.support import load_fixture

from planlint import counts
from planlint.document import PlanDocument


def run(name):
    return counts.run(load_fixture(name))


class NumberWordTest(unittest.TestCase):
    def test_a_digit_and_a_word_both_read_as_the_same_number(self):
        self.assertEqual(counts.as_number("5"), 5)
        self.assertEqual(counts.as_number("five"), 5)
        self.assertEqual(counts.as_number("Fourteen"), 14)
        self.assertIsNone(counts.as_number("several"))


class CountsLintTest(unittest.TestCase):
    def test_the_clean_plan_reports_nothing(self):
        result = run("clean_plan.md")

        self.assertEqual(result.findings, [])
        self.assertEqual(result.examined, 10)

    def test_every_miscount_is_reported_and_nothing_else(self):
        result = run("neg_counts.md")

        self.assertEqual(
            sorted((f.rule, f.evidence) for f in result.findings),
            [
                (
                    "conditional-count-mismatch",
                    "the plan says 4 conditional tasks; section 24.4's table holds 1",
                ),
                (
                    "cross-track-edge-count-mismatch",
                    "section 7.6 assertion 7 says 3 cross-track edges inside one wave; "
                    "the `Depends:` graph holds 2 (BBB-1 → AAA-2; CCC-1 → AAA-2)",
                ),
                (
                    "cross-track-edge-missing-from-7-4",
                    "BBB-1 → AAA-2, both wave 2 (order 2); section 7.4's table "
                    "does not carry it",
                ),
                (
                    "cross-track-edge-missing-from-7-4",
                    "CCC-1 → AAA-2, both wave 2 (order 2); section 7.4's table "
                    "does not carry it",
                ),
                (
                    "cross-track-edge-not-in-graph",
                    "section 7.3's cross-track column lists BBB-1 → CCC-1, both wave "
                    "2 (order 2); BBB-1's `Depends:` line does not name CCC-1",
                ),
                (
                    "cross-track-edge-undeclared",
                    "BBB-1 → AAA-2, both wave 2 (order 2); section 7.3's cross-track "
                    "column does not list it",
                ),
                (
                    "cross-track-edge-undeclared",
                    "CCC-1 → AAA-2, both wave 2 (order 2); section 7.3's cross-track "
                    "column does not list it",
                ),
                (
                    "total-count-mismatch",
                    "section 24.1 says 9 task blocks; the document holds 4",
                ),
                (
                    "total-is-not-the-sum",
                    "section 24.1's track rows sum to 5; its total row says 9",
                ),
                (
                    "track-count-mismatch",
                    "section 24.1 says track AAA has 3 tasks; the document holds 2 "
                    "(AAA-1, AAA-2)",
                ),
            ],
        )

    def test_a_document_that_states_no_count_is_a_hard_error(self):
        result = counts.run(
            PlanDocument.from_text(
                "**AAA-1 · A task** — T0\nDepends: none\nCheck: `ctest`\n", name="inline"
            )
        )

        self.assertEqual(
            [(f.rule, f.message) for f in result.findings],
            [("no-input", "the counts lint examined 0 stated claims")],
        )


WAVE_TABLE = """### 7.2 The waves

| Wave | Order | The tasks in it |
|---|---|---|
| 1 | 1 | AAA-1 |
| 2 | 2 | AAA-2, AAA-3, BBB-1, CCC-1 |
"""

TASKS = """## 9. The tasks

**AAA-1 · The first** — T0
Depends: none
Check: `ctest --test-dir build --no-tests=error -R t0_alpha`.

**AAA-2 · The second** — T0
Depends: AAA-1
Check: `ctest --test-dir build --no-tests=error -R t0_beta`.

**AAA-3 · The third** — T0
Depends: AAA-2
Check: `ctest --test-dir build --no-tests=error -R t0_gamma`.

**BBB-1 · The fourth** — T0
Depends: AAA-2
Check: `ctest --test-dir build --no-tests=error -R t0_delta`.

**CCC-1 · The fifth** — T0
Depends: BBB-1, AAA-1
Check: `ctest --test-dir build --no-tests=error -R t0_epsilon`.
"""


TABLE_7_4 = (
    "| beta | BBB-1 | alpha | AAA-2 | header |\n"
    "| gamma | CCC-1 | beta | BBB-1 | behaviour |\n"
)


def inline(column, statement=None, table=TABLE_7_4):
    """A document whose section 7.3 column is the only claim under test.

    The graph carries one intra-track edge inside wave 2 (AAA-3 → AAA-2), one
    cross-track edge that crosses a wave (CCC-1 → AAA-1), and two cross-track
    edges inside wave 2 (BBB-1 → AAA-2 and CCC-1 → BBB-1). Only the last two
    belong to the derived set.

    Section 7.4's table comes LAST so that a test which varies it moves no line
    number the other tests assert. It defaults to the derived set exactly, so a
    test that says nothing about section 7.4 gets no finding from it.
    """
    middle = "" if statement is None else statement + "\n\n"
    text = (
        "# Inline plan\n\n"
        + WAVE_TABLE
        + "\n### 7.3 Track dependencies\n\n"
        + "| Track | Depends on | Cross-track task edges |\n|---|---|---|\n"
        + column
        + "\n\n"
        + middle
        + TASKS
        + "\n### 7.4 What the graph really says\n\n"
        + "| From (track) | Task | To (track) | Task | Kind |\n|---|---|---|---|---|\n"
        + table
    )
    return PlanDocument.from_text(text, name="inline")


class CrossTrackDerivationTest(unittest.TestCase):
    """The set comes from the `Depends:` graph. Section 7.3's column is the
    other operand and never the source."""

    def test_the_graph_yields_every_in_wave_edge_that_crosses_a_track(self):
        doc = load_fixture("clean_plan.md")

        self.assertEqual(
            counts.graph_cross_track_edges(doc),
            {("BBB-1", "AAA-2"): 109, ("DDD-1", "AAA-2"): 128},
        )

    def test_section_7_3_yields_the_same_set_out_of_its_own_column(self):
        doc = load_fixture("clean_plan.md")

        self.assertEqual(
            counts.declared_cross_track_edges(doc),
            {("BBB-1", "AAA-2"): 48, ("DDD-1", "AAA-2"): 49},
        )

    def test_section_7_4_yields_the_same_set_out_of_its_own_table(self):
        """The same two filters, applied to the second table.

        The fixture's table carries a same-track row and a wave-crossing row
        beside the two real edges, so dropping either filter changes this set.
        """
        doc = load_fixture("clean_plan.md")

        self.assertEqual(
            counts.table_cross_track_edges(doc),
            {("BBB-1", "AAA-2"): 62, ("DDD-1", "AAA-2"): 73},
        )

    def test_an_edge_section_7_4_states_twice_is_one_edge_at_its_first_row(self):
        """Section 7.4's table may state one edge twice, and the line a finding
        carries has to send a reader to the FIRST row that states it."""
        doc = inline(
            "| beta | alpha | BBB-1 → AAA-2 |\n| gamma | beta | CCC-1 → BBB-1 |",
            table=TABLE_7_4 + "| beta | BBB-1 | alpha | AAA-2 | header |\n",
        )

        result = counts.run(doc)

        self.assertEqual(
            counts.table_cross_track_edges(doc),
            {("BBB-1", "AAA-2"): 43, ("CCC-1", "BBB-1"): 44},
        )
        self.assertEqual(result.findings, [])

    def test_an_edge_whose_two_ends_share_a_track_is_no_cross_track_edge(self):
        doc = inline(
            "| alpha | nothing | AAA-3 → AAA-2 |\n| beta | alpha | BBB-1 → AAA-2 |"
        )

        self.assertEqual(
            counts.declared_cross_track_edges(doc), {("BBB-1", "AAA-2"): 15}
        )
        self.assertEqual(
            counts.graph_cross_track_edges(doc),
            {("BBB-1", "AAA-2"): 31, ("CCC-1", "BBB-1"): 35},
        )

    def test_a_self_loop_in_the_column_is_no_cross_track_edge(self):
        doc = inline(
            "| alpha | nothing | AAA-3 → AAA-3 |\n| beta | alpha | BBB-1 → AAA-2 |"
        )

        self.assertEqual(
            counts.declared_cross_track_edges(doc), {("BBB-1", "AAA-2"): 15}
        )

    def test_an_edge_the_column_states_twice_is_one_edge(self):
        doc = inline(
            "| beta | alpha | BBB-1 → AAA-2 |\n| gamma | beta | BBB-1 → AAA-2 |"
        )

        self.assertEqual(
            counts.declared_cross_track_edges(doc), {("BBB-1", "AAA-2"): 14}
        )

    def test_an_edge_that_crosses_a_wave_is_outside_the_set_on_both_sides(self):
        doc = inline("| beta | alpha | BBB-1 → AAA-1 |")

        self.assertEqual(counts.declared_cross_track_edges(doc), {})
        self.assertEqual(
            counts.graph_cross_track_edges(doc),
            {("BBB-1", "AAA-2"): 30, ("CCC-1", "BBB-1"): 34},
        )


class CrossTrackSetTest(unittest.TestCase):
    """Section 7.6 assertion 13: the set derived from the graph equals section
    7.3's column exactly. A set is compared against a set, in both directions."""

    def test_an_edge_the_graph_holds_and_the_column_omits_is_reported(self):
        doc = inline("| beta | alpha | BBB-1 → AAA-2 |")

        result = counts.run(doc)

        self.assertEqual(
            [(f.rule, f.task, f.section, f.line, f.evidence) for f in result.findings],
            [
                (
                    "cross-track-edge-undeclared",
                    "CCC-1",
                    "9. The tasks",
                    34,
                    "CCC-1 → BBB-1, both wave 2 (order 2); section 7.3's "
                    "cross-track column does not list it",
                )
            ],
        )

    def test_an_edge_the_column_holds_and_the_graph_does_not_is_reported(self):
        doc = inline(
            "| beta | alpha | BBB-1 → AAA-2 |\n"
            "| gamma | beta | CCC-1 → BBB-1; CCC-1 → AAA-2 |"
        )

        result = counts.run(doc)

        self.assertEqual(
            [(f.rule, f.task, f.section, f.line, f.evidence) for f in result.findings],
            [
                (
                    "cross-track-edge-not-in-graph",
                    "CCC-1",
                    "7.3 Track dependencies",
                    15,
                    "section 7.3's cross-track column lists CCC-1 → AAA-2, both "
                    "wave 2 (order 2); CCC-1's `Depends:` line does not name AAA-2",
                )
            ],
        )

    def test_both_directions_are_reported_from_one_run(self):
        doc = inline("| gamma | beta | CCC-1 → AAA-2 |")

        result = counts.run(doc)

        self.assertEqual(
            sorted((f.rule, f.evidence) for f in result.findings),
            [
                (
                    "cross-track-edge-not-in-graph",
                    "section 7.3's cross-track column lists CCC-1 → AAA-2, both "
                    "wave 2 (order 2); CCC-1's `Depends:` line does not name AAA-2",
                ),
                (
                    "cross-track-edge-undeclared",
                    "BBB-1 → AAA-2, both wave 2 (order 2); section 7.3's "
                    "cross-track column does not list it",
                ),
                (
                    "cross-track-edge-undeclared",
                    "CCC-1 → BBB-1, both wave 2 (order 2); section 7.3's "
                    "cross-track column does not list it",
                ),
            ],
        )

    def test_a_column_whose_every_row_crosses_a_wave_is_still_an_examined_claim(self):
        """Both operands are empty and the claim still HELD. A lint that
        counted no input here would report a hard error over a document it
        checked and found consistent."""
        doc = PlanDocument.from_text(
            "# Inline plan\n\n"
            "### 7.2 The waves\n\n"
            "| Wave | Order | The tasks in it |\n|---|---|---|\n"
            "| 1 | 1 | AAA-1 |\n| 2 | 2 | BBB-1 |\n\n"
            "### 7.3 Track dependencies\n\n"
            "| Track | Depends on | Cross-track task edges |\n|---|---|---|\n"
            "| beta | alpha | BBB-1 \u2192 AAA-1 |\n\n"
            "## 9. The tasks\n\n"
            "**AAA-1 \u00b7 The first** \u2014 T0\nDepends: none\n"
            "Check: `ctest --test-dir build --no-tests=error -R t0_alpha`.\n\n"
            "**BBB-1 \u00b7 The second** \u2014 T0\nDepends: AAA-1\n"
            "Check: `ctest --test-dir build --no-tests=error -R t0_beta`.\n",
            name="inline",
        )

        result = counts.run(doc)

        self.assertEqual(counts.graph_cross_track_edges(doc), {})
        self.assertEqual(counts.declared_cross_track_edges(doc), {})
        self.assertEqual(result.findings, [])
        self.assertEqual(result.examined, 1)

    def test_the_set_claim_is_an_examined_input_of_its_own(self):
        doc = inline(
            "| beta | alpha | BBB-1 → AAA-2 |\n| gamma | beta | CCC-1 → BBB-1 |"
        )

        result = counts.run(doc)

        self.assertEqual(result.findings, [])
        self.assertEqual(result.examined, 2)
        self.assertEqual(result.examined_label, "stated claims")


class CrossTrackTableSetTest(unittest.TestCase):
    """Assertion 7's OTHER site. The same derived set is held against section
    7.4's table, in both directions, exactly as it is against 7.3's column."""

    def test_an_edge_the_graph_holds_and_section_7_4_omits_is_reported(self):
        doc = inline(
            "| beta | alpha | BBB-1 → AAA-2 |\n| gamma | beta | CCC-1 → BBB-1 |",
            table="| beta | BBB-1 | alpha | AAA-2 | header |\n",
        )

        result = counts.run(doc)

        self.assertEqual(
            [(f.rule, f.task, f.section, f.line, f.evidence) for f in result.findings],
            [
                (
                    "cross-track-edge-missing-from-7-4",
                    "CCC-1",
                    "9. The tasks",
                    35,
                    "CCC-1 → BBB-1, both wave 2 (order 2); section 7.4's table "
                    "does not carry it",
                )
            ],
        )

    def test_a_section_7_4_row_no_depends_line_declares_is_reported(self):
        doc = inline(
            "| beta | alpha | BBB-1 → AAA-2 |\n| gamma | beta | CCC-1 → BBB-1 |",
            table=TABLE_7_4 + "| gamma | CCC-1 | alpha | AAA-2 | behaviour |\n",
        )

        result = counts.run(doc)

        self.assertEqual(
            [(f.rule, f.task, f.section, f.line, f.evidence) for f in result.findings],
            [
                (
                    "cross-track-row-7-4-not-in-graph",
                    "CCC-1",
                    "7.4 What the graph really says",
                    45,
                    "section 7.4's table carries CCC-1 → AAA-2, both wave 2 "
                    "(order 2); CCC-1's `Depends:` line does not name AAA-2",
                )
            ],
        )

    def test_both_directions_are_reported_from_one_run(self):
        doc = inline(
            "| beta | alpha | BBB-1 → AAA-2 |\n| gamma | beta | CCC-1 → BBB-1 |",
            table="| gamma | CCC-1 | alpha | AAA-2 | behaviour |\n",
        )

        result = counts.run(doc)

        self.assertEqual(
            sorted((f.rule, f.evidence) for f in result.findings),
            [
                (
                    "cross-track-edge-missing-from-7-4",
                    "BBB-1 → AAA-2, both wave 2 (order 2); section 7.4's table "
                    "does not carry it",
                ),
                (
                    "cross-track-edge-missing-from-7-4",
                    "CCC-1 → BBB-1, both wave 2 (order 2); section 7.4's table "
                    "does not carry it",
                ),
                (
                    "cross-track-row-7-4-not-in-graph",
                    "section 7.4's table carries CCC-1 → AAA-2, both wave 2 "
                    "(order 2); CCC-1's `Depends:` line does not name AAA-2",
                ),
            ],
        )

    def test_the_table_claim_is_an_examined_input_of_its_own(self):
        doc = inline(
            "| beta | alpha | BBB-1 → AAA-2 |\n| gamma | beta | CCC-1 → BBB-1 |"
        )

        result = counts.run(doc)

        self.assertEqual(result.findings, [])
        self.assertEqual(result.examined, 2)
        self.assertEqual(result.examined_label, "stated claims")


class CrossTrackWrittenFigureTest(unittest.TestCase):
    """Assertion 7's number is held against the count the GRAPH yields."""

    def test_the_written_figure_is_compared_against_the_derived_count(self):
        doc = inline(
            "| beta | alpha | BBB-1 → AAA-2 |\n| gamma | beta | CCC-1 → BBB-1 |",
            statement="There are three edges, and each one crosses a track inside one wave.",
        )

        result = counts.run(doc)

        self.assertEqual(
            [(f.rule, f.section, f.line, f.evidence) for f in result.findings],
            [
                (
                    "cross-track-edge-count-mismatch",
                    "7.6 The dependency and wave check",
                    17,
                    "section 7.6 assertion 7 says 3 cross-track edges inside one "
                    "wave; the `Depends:` graph holds 2 (BBB-1 → AAA-2; "
                    "CCC-1 → BBB-1)",
                )
            ],
        )

    def test_a_figure_that_matches_the_derived_count_is_no_finding(self):
        doc = inline(
            "| beta | alpha | BBB-1 → AAA-2 |\n| gamma | beta | CCC-1 → BBB-1 |",
            statement="There are two edges, and each one crosses a track inside one wave.",
        )

        result = counts.run(doc)

        self.assertEqual(result.findings, [])
        self.assertEqual(result.examined, 3)


class CrossWaveArrowTest(unittest.TestCase):
    """The wave filter narrows the SUBJECT, and a wrong arrow target does not
    respect that narrowing.

    Every rule above judges an edge only when its two ends sit in one wave.
    Eight arrows in the plan's own section 7.3 named a target the `Depends:`
    graph does not hold, every one of them crossed a wave, and the lint
    reported clean throughout while its operands were non-empty. A true pass
    over a subject narrower than the defect is the shape this class widens.

    ONE direction is widened and not both. Section 7.3's opening states that a
    track's contract inputs are listed once for the track and are not repeated
    per task, so the column OMITS cross-track graph edges BY DESIGN, in bulk. A
    rule widened in that direction would report every one of them against a
    document obeying its own stated convention, which is worse than no rule at
    all. An arrow is the other direction: it is a claim about a `Depends:` line
    whatever wave its two ends sit in, and a claim carries no licence to be
    wrong outside a wave.

    The last test in this class is the guard on that asymmetry.
    """

    def test_a_7_3_arrow_across_waves_that_no_depends_line_declares_is_reported(self):
        doc = inline(
            "| beta | alpha | BBB-1 → AAA-2 |\n"
            "| gamma | beta | CCC-1 → BBB-1 |\n"
            "| alpha | beta | AAA-1 → BBB-1 |"
        )

        self.assertEqual(
            [
                (f.rule, f.task, f.section, f.line, f.severity, f.evidence)
                for f in counts.run(doc).findings
            ],
            [
                (
                    "cross-track-edge-not-in-graph-across-waves",
                    "AAA-1",
                    "7.3 Track dependencies",
                    16,
                    "ERROR",
                    "section 7.3's cross-track column lists AAA-1 → BBB-1, "
                    "AAA-1 in wave 1 (order 1) and BBB-1 in wave 2 (order 2); "
                    "AAA-1's `Depends:` line does not name BBB-1",
                )
            ],
        )

    def test_a_7_4_row_across_waves_that_no_depends_line_declares_is_reported(self):
        doc = inline(
            "| beta | alpha | BBB-1 → AAA-2 |\n| gamma | beta | CCC-1 → BBB-1 |",
            table=TABLE_7_4 + "| alpha | AAA-1 | beta | BBB-1 | behaviour |\n",
        )

        self.assertEqual(
            [
                (f.rule, f.task, f.section, f.line, f.severity, f.evidence)
                for f in counts.run(doc).findings
            ],
            [
                (
                    "cross-track-row-7-4-not-in-graph-across-waves",
                    "AAA-1",
                    "7.4 What the graph really says",
                    45,
                    "ERROR",
                    "section 7.4's table carries AAA-1 → BBB-1, AAA-1 in wave 1 "
                    "(order 1) and BBB-1 in wave 2 (order 2); AAA-1's "
                    "`Depends:` line does not name BBB-1",
                )
            ],
        )

    def test_an_arrow_across_waves_the_graph_holds_is_no_finding(self):
        """`CCC-1 → AAA-1` is the inline document's wave-crossing edge and the
        `Depends:` graph holds it. Stating it in both sites is correct, and a
        rule that reported it would fire on the plan's own `usbhost` row, whose
        every arrow crosses a wave by the row's own statement."""
        doc = inline(
            "| beta | alpha | BBB-1 → AAA-2 |\n"
            "| gamma | beta | CCC-1 → BBB-1 |\n"
            "| gamma | alpha | CCC-1 → AAA-1 |",
            table=TABLE_7_4 + "| gamma | CCC-1 | alpha | AAA-1 | behaviour |\n",
        )

        self.assertEqual(counts.run(doc).findings, [])

    def test_a_graph_edge_across_waves_that_neither_site_states_is_no_finding(self):
        """The limit, asserted rather than described.

        `CCC-1 → AAA-1` is in the graph and in neither table here, which is
        exactly what section 7.3's track-level convention licenses. A widening
        of the omission direction would redden this, and would redden the real
        plan once for every track-level input it declines to repeat.
        """
        doc = inline(
            "| beta | alpha | BBB-1 → AAA-2 |\n| gamma | beta | CCC-1 → BBB-1 |"
        )

        self.assertEqual(counts.run(doc).findings, [])

    def test_an_end_the_wave_table_places_nowhere_is_still_held_to_the_graph(self):
        """An identifier no wave row names has no order to compare, so every
        in-wave rule is silent on it. That silence is what let a wrong arrow
        target hide; here the arrow is judged anyway and the evidence says the
        wave table places the end nowhere rather than inventing an order."""
        doc = inline(
            "| beta | alpha | BBB-1 → AAA-2 |\n"
            "| gamma | beta | CCC-1 → BBB-1 |\n"
            "| alpha | beta | AAA-3 → BBB-1 |",
            table=TABLE_7_4,
        )
        doc.wave_of.pop("AAA-3")

        self.assertEqual(
            [(f.rule, f.task, f.evidence) for f in counts.run(doc).findings],
            [
                (
                    "cross-track-edge-not-in-graph-across-waves",
                    "AAA-3",
                    "section 7.3's cross-track column lists AAA-3 → BBB-1, "
                    "AAA-3 in no row of section 7.2's wave table and BBB-1 in "
                    "wave 2 (order 2); AAA-3's `Depends:` line does not name "
                    "BBB-1",
                )
            ],
        )


if __name__ == "__main__":
    unittest.main()
