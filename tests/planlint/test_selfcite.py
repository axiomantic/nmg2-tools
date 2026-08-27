"""Tests for the line-number citation lint.

The document cites its OWN line numbers, and it grows by appending, so every
citation below an insertion point goes stale in silence. These tests hold the
two halves the lint must get right at once: WHAT it recognises as a citation,
and WHETHER the number it recognised points at what the citation claims.

The negative controls are the shapes a scan for four-digit numbers would
swallow — a CRC, a sha fragment, and a line reference into another document.
They are asserted to yield NO citation, because a lint that fires on those
would be turned off inside a week.
"""

import unittest

from tests.planlint.support import load_fixture

from planlint import selfcite
from planlint.document import PlanDocument

HEAD = """# Inline plan

## 9. The tasks

**AAA-1 · The first** — T0
Files: `tests/t0_alpha.cpp`, `tests/tests_core.cmake`

**AAA-2 · The second** — T0
Files: `tests/tests_core.cmake`

## 24.7 The citations
"""

# `tests/t0_alpha.cpp` is named by the `Files:` line on 6 and by nothing else.
# `tests/tests_core.cmake` is named by 6 and by 9. Line 10 is blank, which is
# the live defect's own shape: the stale figure lands on nothing at all.
ALPHA_LINE = 6
CMAKE_LINES = (6, 9)
BLANK_LINE = 10
PROSE_LINE = 12
PROSE_SECTION = "24.7 The citations"

# The clause is section 24.6 row W3-434's own, copied WORD FOR WORD out of the
# plan at `nmg2-artifacts` commit 42a9b99, blob 35628d4. Its first three figures
# are right against that document and its fourth is wrong; what is asserted here
# is only that the recogniser reads the real sentence, not the resolution.
LIVE_CLAUSE = (
    "Against that population: `tests/abi_smoke_symbols.inc` appears on **0**; "
    "`tests/abi_stub.c` on **4** (lines 4018, 4316, 4694, 9271); "
    "`include/mcf5307.h` on **4**; `tests/t_control_registers.nim` on **1** "
    "(line 4694, CPU-29's own)."
)


def inline(prose):
    """A document whose only citation is `prose`, landing on `PROSE_LINE`."""
    return PlanDocument.from_text(HEAD + prose + "\n", name="inline")


def reported(result):
    return [
        (f.rule, f.severity, f.section, f.line, f.message, f.evidence)
        for f in result.findings
    ]


class CitationScanTest(unittest.TestCase):
    def test_a_citation_yields_its_subject_its_figures_and_its_line(self):
        doc = inline("`tests/tests_core.cmake` on **2** (lines 6, 9).")

        self.assertEqual(
            selfcite.citations_in(doc),
            [
                selfcite.Citation(
                    path="tests/tests_core.cmake",
                    figures=(6, 9),
                    line=PROSE_LINE,
                    text="(lines 6, 9)",
                )
            ],
        )

    def test_a_singular_citation_reads_the_numbers_and_stops_at_the_prose(self):
        """`(line 4694, CPU-29's own)` is the live spelling. The trailing
        clause is not a figure and must not be read as one."""
        doc = inline("`tests/t0_alpha.cpp` on **1** (line 6, AAA-1's own).")

        self.assertEqual(
            selfcite.citations_in(doc),
            [
                selfcite.Citation(
                    path="tests/t0_alpha.cpp",
                    figures=(6,),
                    line=PROSE_LINE,
                    text="(line 6, AAA-1's own)",
                )
            ],
        )

    def test_the_live_row_s_own_sentence_is_read_as_two_citations(self):
        doc = inline(LIVE_CLAUSE)

        self.assertEqual(
            selfcite.citations_in(doc),
            [
                selfcite.Citation(
                    path="tests/abi_stub.c",
                    figures=(4018, 4316, 4694, 9271),
                    line=PROSE_LINE,
                    text="(lines 4018, 4316, 4694, 9271)",
                ),
                selfcite.Citation(
                    path="tests/t_control_registers.nim",
                    figures=(4694,),
                    line=PROSE_LINE,
                    text="(line 4694, CPU-29's own)",
                ),
            ],
        )

    def test_a_crc_a_sha_fragment_and_a_foreign_line_reference_are_not_citations(self):
        """The three shapes a scan for four-digit numbers would swallow. Each
        one is a real span of the live plan."""
        doc = inline(
            "The `Bad CRC 0x8926 0x3410` transcript, the citation-repair commit "
            "`ae9157e`, and `source/MCF5307UM.textlayer.txt:9046` — with the "
            "block size for CS[2:7] fixed at 2 MB (textlayer:9247)."
        )

        self.assertEqual(selfcite.citations_in(doc), [])

    def test_a_backtick_between_the_subject_and_the_citation_breaks_the_binding(self):
        """The subject is the NEAREST preceding backticked path with nothing
        backticked in between. A citation whose subject is not decidable must
        arrive at the lint as unresolvable, never bound to a distant path."""
        doc = inline("`tests/t0_alpha.cpp` and then `the other thing` (lines 6, 9).")

        self.assertEqual(
            selfcite.citations_in(doc),
            [
                selfcite.Citation(
                    path="", figures=(6, 9), line=PROSE_LINE, text="(lines 6, 9)"
                )
            ],
        )


class ResolutionTest(unittest.TestCase):
    def test_a_figure_that_names_the_files_line_it_claims_is_clean(self):
        doc = inline("`tests/tests_core.cmake` on **2** (lines 6, 9).")

        result = selfcite.run(doc)

        self.assertEqual(reported(result), [])
        self.assertEqual(result.examined, len(CMAKE_LINES))
        self.assertIs(result.failed, False)

    def test_one_stale_figure_beside_three_sound_ones_reports_exactly_one(self):
        """The known positive and the known negatives, in ONE citation, through
        ONE code path. The live defect's shape: the figures above the insertion
        point are right and the one below it is not."""
        doc = inline("`tests/tests_core.cmake` on **3** (lines 6, 9, 10).")

        result = selfcite.run(doc)

        self.assertEqual(
            reported(result),
            [
                (
                    "line-citation-unresolved",
                    "ERROR",
                    PROSE_SECTION,
                    PROSE_LINE,
                    "a cited line number does not name what the citation claims",
                    "the citation `(lines 6, 9, 10)` claims line 10 is a `Files:` "
                    "line naming `tests/tests_core.cmake`; line 10 is blank; that "
                    "path is named by the `Files:` lines 6, 9",
                )
            ],
        )
        self.assertEqual(result.examined, 3)

    def test_a_figure_naming_a_files_line_for_another_file_is_reported(self):
        doc = inline("`tests/t0_alpha.cpp` on **2** (lines 6, 9).")

        result = selfcite.run(doc)

        self.assertEqual(
            reported(result),
            [
                (
                    "line-citation-unresolved",
                    "ERROR",
                    PROSE_SECTION,
                    PROSE_LINE,
                    "a cited line number does not name what the citation claims",
                    "the citation `(lines 6, 9)` claims line 9 is a `Files:` line "
                    "naming `tests/t0_alpha.cpp`; line 9 is a `Files:` line that "
                    "does not name it; that path is named by the `Files:` line 6",
                )
            ],
        )

    def test_a_figure_past_the_end_of_the_document_is_reported(self):
        doc = inline("`tests/t0_alpha.cpp` on **2** (lines 6, 999).")

        result = selfcite.run(doc)

        self.assertEqual(
            reported(result),
            [
                (
                    "line-citation-unresolved",
                    "ERROR",
                    PROSE_SECTION,
                    PROSE_LINE,
                    "a cited line number does not name what the citation claims",
                    "the citation `(lines 6, 999)` claims line 999 is a `Files:` "
                    "line naming `tests/t0_alpha.cpp`; the document ends at line "
                    "12; that path is named by the `Files:` line 6",
                )
            ],
        )

    def test_a_path_the_document_names_nowhere_says_so_rather_than_guessing(self):
        doc = inline("`tests/t9_omega.cpp` on **1** (line 6).")

        result = selfcite.run(doc)

        self.assertEqual(
            reported(result),
            [
                (
                    "line-citation-unresolved",
                    "ERROR",
                    PROSE_SECTION,
                    PROSE_LINE,
                    "a cited line number does not name what the citation claims",
                    "the citation `(line 6)` claims line 6 is a `Files:` line "
                    "naming `tests/t9_omega.cpp`; line 6 is a `Files:` line that "
                    "does not name it; no `Files:` line in this document names "
                    "that path",
                )
            ],
        )

    def test_a_citation_with_no_decidable_subject_is_reported_and_never_passed(self):
        """The lint says what it cannot resolve. Passing it would be the same
        silence the lint exists to end."""
        doc = inline("The same command returns four elsewhere (lines 6, 9).")

        result = selfcite.run(doc)

        self.assertEqual(
            reported(result),
            [
                (
                    "line-citation-unresolvable",
                    "ERROR",
                    PROSE_SECTION,
                    PROSE_LINE,
                    "a line-number citation states no file this tool can resolve",
                    "the citation `(lines 6, 9)` is preceded by no backticked "
                    "path, so what its numbers claim is not decidable",
                )
            ],
        )
        self.assertEqual(result.examined, 2)


class ExaminedPopulationTest(unittest.TestCase):
    def test_one_unit_is_one_cited_line_number(self):
        doc = inline(
            "`tests/tests_core.cmake` on **2** (lines 6, 9), and "
            "`tests/t0_alpha.cpp` on **1** (line 6)."
        )

        result = selfcite.run(doc)

        self.assertEqual(reported(result), [])
        self.assertEqual(result.examined, 3)
        self.assertEqual(result.examined_label, "cited line numbers")

    def test_a_document_with_no_citation_is_a_hard_error_and_never_a_pass(self):
        doc = inline("This section cites no line number at all.")

        result = selfcite.run(doc)

        self.assertEqual(
            reported(result),
            [
                (
                    "no-input",
                    "ERROR",
                    "",
                    0,
                    "the selfcite lint examined 0 cited line numbers",
                    "",
                )
            ],
        )
        self.assertIs(result.failed, True)

    def test_the_report_names_what_the_lint_does_not_reach(self):
        doc = inline("`tests/tests_core.cmake` on **2** (lines 6, 9).")

        self.assertEqual(
            selfcite.run(doc).notice,
            "a line reference into ANOTHER document — the `path:NNNN` form — is "
            "out of scope and is examined by nothing here.",
        )


class CleanPlanTest(unittest.TestCase):
    def test_the_clean_plan_reports_nothing(self):
        result = selfcite.run(load_fixture("clean_plan.md"))

        self.assertEqual(reported(result), [])

    def test_the_clean_plan_carries_the_citations_this_lint_reads(self):
        """An empty scan makes the assertion above pass while examining
        nothing, so the population the fixture offers is asserted too."""
        result = selfcite.run(load_fixture("clean_plan.md"))

        self.assertEqual(result.examined, 6)


if __name__ == "__main__":
    unittest.main()
