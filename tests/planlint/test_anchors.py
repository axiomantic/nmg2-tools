"""Tests for the anchored-figure lint.

A figure the tool DERIVES may also be written out in prose. The lint holds the
written word against the derived value, and it reaches only the restatements an
anchor marks.
"""

import unittest

from tests.planlint.support import load_fixture

from planlint import anchors
from planlint.document import PlanDocument

TASKS = """
## 9. The tasks

**AAA-1 · The first** — T0
Depends: none
Check: `ctest --test-dir build --no-tests=error -R t0_alpha`.

**AAA-2 · The second** — T0
Depends: AAA-1
Check: `ctest --test-dir build --no-tests=error -R t0_beta`.

**BBB-1 · The third** — T0
Depends: AAA-2
Check: `ctest --test-dir build --no-tests=error -R t0_gamma`.

**CCC-1 · The fourth** — T0
Depends: BBB-1
Check: `ctest --test-dir build --no-tests=error -R t0_delta`.
"""

HEAD = """# Inline plan

### 7.2 The waves

| Wave | Order | The tasks in it |
|---|---|---|
| 1 | 1 | AAA-1 |
| 2 | 2 | AAA-2, BBB-1, CCC-1 |

### 7.6 The dependency and wave check

"""

PROSE_LINE = 12
PROSE_SECTION = "7.6 The dependency and wave check"


def inline(prose):
    """A document whose derived in-wave cross-track edge count is two.

    BBB-1 → AAA-2 and CCC-1 → BBB-1 each cross a track inside wave 2. `prose`
    is the only thing under test and it lands on `PROSE_LINE`.
    """
    return PlanDocument.from_text(HEAD + prose + "\n" + TASKS, name="inline")


def reported(result):
    return [
        (f.rule, f.severity, f.section, f.line, f.message, f.evidence)
        for f in result.findings
    ]


class AnchorScanTest(unittest.TestCase):
    def test_an_anchor_yields_its_key_its_token_and_its_line(self):
        doc = inline("<!-- derived: cross-track-edge-count -->Two edges cross.")

        self.assertEqual(
            anchors.anchors_in(doc),
            [
                anchors.Anchor(
                    key="cross-track-edge-count", token="Two", line=PROSE_LINE
                )
            ],
        )


class StaleFigureTest(unittest.TestCase):
    def test_a_word_that_matches_the_derived_value_is_no_finding(self):
        result = anchors.run(
            inline("<!-- derived: cross-track-edge-count -->Two edges cross.")
        )

        self.assertEqual(result.findings, [])
        self.assertEqual(result.examined, 1)
        self.assertEqual(result.examined_label, "anchored figures")

    def test_a_word_that_does_not_match_the_derived_value_is_reported(self):
        result = anchors.run(
            inline("<!-- derived: cross-track-edge-count -->Fifteen edges cross.")
        )

        self.assertEqual(
            reported(result),
            [
                (
                    "derived-figure-stale",
                    "ERROR",
                    PROSE_SECTION,
                    PROSE_LINE,
                    "a prose restatement of a derived figure does not equal the "
                    "value the tool derives",
                    "the anchor `cross-track-edge-count` restates the figure as "
                    "`Fifteen`, which reads as 15; the tool derives 2",
                )
            ],
        )


class UnparsableTokenTest(unittest.TestCase):
    """A token the tool cannot read is REPORTED. Skipping it silently is the
    defect the anchor exists to close, arriving one level down."""

    def test_a_digit_reads_as_the_same_value_as_its_word(self):
        result = anchors.run(
            inline("<!-- derived: cross-track-edge-count -->2 edges cross.")
        )

        self.assertEqual(result.findings, [])
        self.assertEqual(result.examined, 1)

    def test_a_word_outside_the_bounded_list_is_reported(self):
        result = anchors.run(
            inline("<!-- derived: cross-track-edge-count -->several edges cross.")
        )

        self.assertEqual(
            reported(result),
            [
                (
                    "derived-figure-unparsed",
                    "ERROR",
                    PROSE_SECTION,
                    PROSE_LINE,
                    "an anchor marks a token that is not a number this tool reads",
                    "the anchor `cross-track-edge-count` marks `several`, which is "
                    "neither a digit nor a number word this tool reads",
                )
            ],
        )

    def test_an_anchor_followed_by_markup_rather_than_a_number_is_reported(self):
        """`**Two` is the shape that makes a silent skip tempting: the number is
        RIGHT THERE and the anchor is one character too far to the left."""
        result = anchors.run(
            inline("<!-- derived: cross-track-edge-count -->**Two edges cross.**")
        )

        self.assertEqual(
            reported(result),
            [
                (
                    "derived-figure-unparsed",
                    "ERROR",
                    PROSE_SECTION,
                    PROSE_LINE,
                    "an anchor marks a token that is not a number this tool reads",
                    "the anchor `cross-track-edge-count` is followed by no letter "
                    "or digit, so it marks no figure",
                )
            ],
        )


class KeyRegistryTest(unittest.TestCase):
    """The anchor names a key the tool computes. A key it does not compute is a
    finding, and a key the tool computes that NO anchor names is a finding too:
    a derived figure whose prose is unanchored is exactly the state this lint
    exists to end, and adding one silently is how it would return."""

    def test_an_anchor_naming_a_key_the_tool_does_not_compute_is_reported(self):
        result = anchors.run(
            inline("<!-- derived: cross-track-edge-kount -->Two edges cross.")
        )

        self.assertEqual(
            reported(result),
            [
                (
                    "derived-figure-unknown-key",
                    "ERROR",
                    PROSE_SECTION,
                    PROSE_LINE,
                    "an anchor names a derived figure this tool does not compute",
                    "the anchor names `cross-track-edge-kount`; this tool computes "
                    "cross-track-edge-count",
                ),
                (
                    "derived-figure-unanchored",
                    "ERROR",
                    "",
                    0,
                    "a derived figure has no anchored restatement in the document",
                    "the tool derives `cross-track-edge-count` as 2 and no "
                    "`<!-- derived: cross-track-edge-count -->` anchor names it",
                ),
            ],
        )

    def test_an_anchor_with_an_empty_key_is_reported_and_never_skipped(self):
        """A malformed anchor must not read as no anchor at all."""
        result = anchors.run(inline("<!-- derived: -->Two edges cross."))

        self.assertEqual(
            [(f.rule, f.line, f.evidence) for f in result.findings],
            [
                (
                    "derived-figure-unknown-key",
                    PROSE_LINE,
                    "the anchor names ``; this tool computes cross-track-edge-count",
                ),
                (
                    "derived-figure-unanchored",
                    0,
                    "the tool derives `cross-track-edge-count` as 2 and no "
                    "`<!-- derived: cross-track-edge-count -->` anchor names it",
                ),
            ],
        )

    def test_a_document_with_no_anchor_at_all_is_reported_twice_over(self):
        """The per-key finding names WHICH figure lost its anchor. The
        run-level guard makes an empty anchor set a hard error rather than a
        clean report over nothing."""
        result = anchors.run(inline("Two edges cross a track inside one wave."))

        self.assertEqual(
            [(f.rule, f.message) for f in result.findings],
            [
                (
                    "derived-figure-unanchored",
                    "a derived figure has no anchored restatement in the document",
                ),
                ("no-input", "the anchors lint examined 0 anchored figures"),
            ],
        )
        self.assertEqual(result.examined, 0)


class EveryAnchorTest(unittest.TestCase):
    """Every anchor is checked, not the first one that names a key. The defect
    that opened this lint was three restatements of one figure, of which a
    check that stopped at the first would have cleared two."""

    def test_a_later_anchor_of_a_key_an_earlier_anchor_already_named_is_checked(
        self,
    ):
        result = anchors.run(
            inline(
                "<!-- derived: cross-track-edge-count -->Two edges cross.\n"
                "\n"
                "The figure of <!-- derived: cross-track-edge-count -->eleven "
                "is unchanged."
            )
        )

        self.assertEqual(
            [(f.rule, f.line, f.evidence) for f in result.findings],
            [
                (
                    "derived-figure-stale",
                    PROSE_LINE + 2,
                    "the anchor `cross-track-edge-count` restates the figure as "
                    "`eleven`, which reads as 11; the tool derives 2",
                )
            ],
        )
        self.assertEqual(result.examined, 2)

    def test_two_anchors_on_one_line_are_two_anchored_figures(self):
        result = anchors.run(
            inline(
                "It counts <!-- derived: cross-track-edge-count -->ten rather "
                "than <!-- derived: cross-track-edge-count -->nine."
            )
        )

        self.assertEqual(
            [(f.rule, f.line, f.evidence) for f in result.findings],
            [
                (
                    "derived-figure-stale",
                    PROSE_LINE,
                    "the anchor `cross-track-edge-count` restates the figure as "
                    "`ten`, which reads as 10; the tool derives 2",
                ),
                (
                    "derived-figure-stale",
                    PROSE_LINE,
                    "the anchor `cross-track-edge-count` restates the figure as "
                    "`nine`, which reads as 9; the tool derives 2",
                ),
            ],
        )
        self.assertEqual(result.examined, 2)


class ReportTest(unittest.TestCase):
    """The anchor count reaches the report. The trade this lint makes — it
    reads the anchored restatements and no others — is only declared if the
    number of anchors it read is visible on a clean run."""

    def test_a_clean_run_states_how_many_anchors_it_examined(self):
        result = anchors.run(
            inline(
                "<!-- derived: cross-track-edge-count -->Two edges cross.\n"
                "\n"
                "Two again: <!-- derived: cross-track-edge-count -->2."
            )
        )

        self.assertEqual(
            result.report(), "anchors: clean (2 anchored figures examined)\n"
        )


class NegativeFixtureTest(unittest.TestCase):
    def test_the_committed_negative_fixture_reports_each_defect_it_carries(self):
        result = anchors.run(load_fixture("neg_anchors.md"))

        self.assertEqual(
            [(f.rule, f.section, f.line, f.evidence) for f in result.findings],
            [
                (
                    "derived-figure-stale",
                    "7.6 The dependency and wave check",
                    16,
                    "the anchor `cross-track-edge-count` restates the figure as "
                    "`Fifteen`, which reads as 15; the tool derives 2",
                ),
                (
                    "derived-figure-unparsed",
                    "7.6 The dependency and wave check",
                    20,
                    "the anchor `cross-track-edge-count` marks `several`, which is "
                    "neither a digit nor a number word this tool reads",
                ),
                (
                    "derived-figure-unknown-key",
                    "7.6 The dependency and wave check",
                    24,
                    "the anchor names `cross-track-edge-kount`; this tool computes "
                    "cross-track-edge-count",
                ),
            ],
        )
        self.assertEqual(result.examined, 3)

    def test_the_clean_fixture_reports_nothing_and_examines_its_anchors(self):
        result = anchors.run(load_fixture("clean_plan.md"))

        self.assertEqual(result.findings, [])
        self.assertEqual(result.examined, 1)


if __name__ == "__main__":
    unittest.main()
