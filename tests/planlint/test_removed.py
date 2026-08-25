"""Tests for the removed-mechanism lint (section 7.7 measurements 7 and 8).

The calibration is the point of this file. Section 24.6 row W3-4 named six
tasks, row W3-18 re-decided two of them OUT of the class, and that split is a
discriminator proof this project already owned and had not spent. A lint that
flags all six proves nothing. Both directions are asserted here: the positive
fixture must be reported, the negative fixture must be spared, and the negative
fixture is the half that is VERBATIM, because sparing is the direction a wrong
lint fails in.
"""

import re
import unittest

from tests.planlint.support import load_fixture

from planlint import cli, removed
from planlint.document import PlanDocument

RULE = "check-predicate-removed-by-default-build"

MESSAGE = (
    "a Check: predicate names assert(), which NDEBUG removes from the default "
    "build, so the check reports PASS against a tree in which the property was "
    "never written; the block names no build type that keeps it "
    "(§7.7 measurements 7 and 8)"
)


def run(name, **kwargs):
    return removed.run(load_fixture(name), **kwargs)


def tuples(result):
    return [(f.rule, f.task, f.evidence) for f in result.findings]


class NegativeFixtureTest(unittest.TestCase):
    """The sparing direction, and the fixture that carries it is verbatim."""

    def test_the_negative_fixture_reports_nothing_over_a_non_zero_population(self):
        result = run("neg_removed_mechanism.md")

        self.assertEqual(result.findings, [])
        self.assertEqual(result.examined, 4)
        self.assertEqual(result.examined_label, "Check: blocks")

    def test_the_lints_own_task_block_is_not_among_the_findings(self):
        """The self-consistency case. TOOL-14's own `Check:` block is carried
        verbatim in the negative fixture, so this is a checked fact and not an
        intention."""
        result = run("neg_removed_mechanism.md")

        self.assertEqual([f.task for f in result.findings if f.task == "TOOL-14"], [])


class PositiveFixtureTest(unittest.TestCase):
    def test_the_positive_fixture_reports_the_five_blocks_and_no_other(self):
        result = run("pos_removed_mechanism.md")

        self.assertEqual(
            sorted((f.rule, f.task) for f in result.findings),
            [
                (RULE, "BRD-17"),
                (RULE, "DSP-7"),
                (RULE, "SCH-20"),
                (RULE, "SCH-28"),
                (RULE, "SCH-7"),
            ],
        )
        self.assertEqual(result.examined, 5)

    def test_the_reconstructed_brd17_block_is_reported(self):
        self.assertIn(
            (
                RULE,
                "BRD-17",
                "The registered test drives more words than the capacity in one "
                "quantum and asserts that no assertion trips.",
            ),
            tuples(run("pos_removed_mechanism.md")),
        )

    def test_the_reconstructed_sch7_block_is_reported(self):
        self.assertIn(
            (RULE, "SCH-7", "The re-entry is caught by an `assert()` in the serial executor."),
            tuples(run("pos_removed_mechanism.md")),
        )

    def test_the_reconstructed_sch20_block_is_reported(self):
        self.assertIn(
            (
                RULE,
                "SCH-20",
                "The four accessors reject an index above `dspCount`, and the test "
                "drives that case and the rejection is an assertion in the accessor.",
            ),
            tuples(run("pos_removed_mechanism.md")),
        )

    def test_the_reconstructed_sch28_block_is_reported(self):
        self.assertIn(
            (
                RULE,
                "SCH-28",
                "Ownership moves exactly once, and the registered test calls an "
                "audio-thread method from the boot thread and asserts the ownership "
                "assertion trips.",
            ),
            tuples(run("pos_removed_mechanism.md")),
        )

    def test_the_verbatim_dsp7_block_is_reported_by_name(self):
        """The live-expectation case, and the one the `kept_by` exclusion is
        falsifiable through: DSP-7 names `Release` and `NDEBUG` in the sentence
        that DIAGNOSES its defect and names no build type that keeps the
        mechanism."""
        self.assertIn(
            (
                RULE,
                "DSP-7",
                "The test arms one DMA channel on each and asserts no assertion trips.",
            ),
            tuples(run("pos_removed_mechanism.md")),
        )


class FindingEvidenceTest(unittest.TestCase):
    """A finding carries its evidence. A message that merely names the task
    sends a reader looking for the sentence."""

    def lines(self):
        return load_fixture("pos_removed_mechanism.md").lines

    def test_every_finding_names_a_clause_the_detection_itself_read(self):
        doc = load_fixture("pos_removed_mechanism.md")
        result = removed.run(doc)

        self.assertEqual(
            [f.task for f in result.findings if f.evidence not in doc.task(f.task).check_text],
            [],
        )

    def test_every_finding_is_an_error_carrying_its_section_and_message(self):
        result = run("pos_removed_mechanism.md")

        self.assertEqual(
            sorted((f.task, f.severity, f.section, f.message) for f in result.findings),
            [
                ("BRD-17", "ERROR", "9. The tasks", MESSAGE),
                ("DSP-7", "ERROR", "9. The tasks", MESSAGE),
                ("SCH-20", "ERROR", "9. The tasks", MESSAGE),
                ("SCH-28", "ERROR", "9. The tasks", MESSAGE),
                ("SCH-7", "ERROR", "9. The tasks", MESSAGE),
            ],
        )

    def test_every_finding_names_the_fixture_line_its_clause_sits_on(self):
        result = run("pos_removed_mechanism.md")

        self.assertEqual(
            sorted((f.task, f.line) for f in result.findings),
            [
                ("BRD-17", 38),
                ("DSP-7", 62),
                ("SCH-20", 50),
                ("SCH-28", 56),
                ("SCH-7", 44),
            ],
        )

    def test_every_evidence_string_is_a_substring_of_the_line_it_names(self):
        lines = self.lines()
        result = run("pos_removed_mechanism.md")

        self.assertEqual(
            [f.task for f in result.findings if f.evidence not in lines[f.line - 1]],
            [],
        )


class TranscriptFenceTest(unittest.TestCase):
    """Evidence is quoted from the extent the DETECTION read.

    `check_text` drops every `$ ` transcript fence, so a reader that re-walked
    the raw document lines could quote a shell transcript as the predicate it
    flagged — a line the detection never saw and the lint has no jurisdiction
    over.
    """

    DOCUMENT = (
        "## 9. The tasks\n"
        "\n"
        "**ZZZ-2 · A Check: block that quotes a transcript** — T0\n"
        "Depends: none\n"
        "Check: `ctest --test-dir build --no-tests=error -R ^t0_zzz$`.\n"
        "\n"
        "```\n"
        "$ grep -n 'assert()' src/foo.cpp\n"
        "12:  assert(x);\n"
        "```\n"
        "\n"
        "The registered test drives one case and asserts that no assertion trips.\n"
    )

    def result(self):
        return removed.run(PlanDocument.from_text(self.DOCUMENT, name="synthetic"))

    def test_the_prose_below_the_transcript_is_reported(self):
        self.assertEqual(
            [(f.rule, f.task, f.evidence) for f in self.result().findings],
            [
                (
                    RULE,
                    "ZZZ-2",
                    "The registered test drives one case and asserts that no "
                    "assertion trips.",
                )
            ],
        )

    def test_no_finding_quotes_a_line_inside_the_transcript_fence(self):
        transcript = [
            line for line in self.DOCUMENT.split("\n") if line.startswith(("$ ", "12:"))
        ]

        quoted = [f.evidence for f in self.result().findings]

        self.assertEqual([line for line in transcript if line in quoted], [])


class MechanismTableTest(unittest.TestCase):
    """The mechanism list is a data table the tests drive. Adding member two is
    a row and a fixture, never an edit to `run()`."""

    SYNTHETIC_DOCUMENT = (
        "## 9. The tasks\n"
        "\n"
        "**ZZZ-1 · The invented mechanism** — T0\n"
        "Depends: none\n"
        "Check: `ctest --test-dir build --no-tests=error -R ^t0_zzz$`. "
        "The registered test drives one case and the quantum tripwire fires.\n"
    )

    SYNTHETIC_TABLE = (
        removed.RemovedMechanism(
            mechanism="quantum tripwire",
            clause_pattern=r"(?i)\bquantum tripwire\b",
            removed_by="G2_NO_TRIPWIRE",
            kept_by=r"(?i)\btripwire build\b",
            authority="§0, a passage this project does not carry",
        ),
    )

    def document(self):
        return PlanDocument.from_text(self.SYNTHETIC_DOCUMENT, name="synthetic")

    def test_a_one_row_synthetic_table_reports_its_own_mechanism(self):
        result = removed.run(self.document(), mechanisms=self.SYNTHETIC_TABLE)

        self.assertEqual(
            [(f.rule, f.task, f.evidence) for f in result.findings],
            [
                (
                    RULE,
                    "ZZZ-1",
                    "The registered test drives one case and the quantum tripwire fires.",
                )
            ],
        )
        self.assertEqual(result.examined, 1)

    def test_the_shipped_table_reports_nothing_for_that_document(self):
        result = removed.run(self.document())

        self.assertEqual(result.findings, [])
        self.assertEqual(result.examined, 1)

    def test_a_synthetic_row_spares_a_block_that_names_its_own_kept_by(self):
        text = self.SYNTHETIC_DOCUMENT.replace(
            "the quantum tripwire fires.\n",
            "the quantum tripwire fires.\nA tripwire build keeps it.\n",
        )
        result = removed.run(
            PlanDocument.from_text(text, name="synthetic"), mechanisms=self.SYNTHETIC_TABLE
        )

        self.assertEqual(result.findings, [])
        self.assertEqual(result.examined, 1)

    def test_the_shipped_table_carries_the_assert_row_the_plan_states(self):
        self.assertEqual(
            [
                (m.mechanism, m.clause_pattern, m.removed_by, m.kept_by, m.authority)
                for m in removed.REMOVED_MECHANISMS
            ],
            [
                (
                    "assert()",
                    r"(?i)\bassert\(\)|\bassert(?:ion|ions)\b",
                    "NDEBUG",
                    r"(?i)\bdebug\s+build\b|\bdebug-only\b|\bRelWithDebInfo\b"
                    r"|\bCMAKE_BUILD_TYPE\s*=\s*Debug\b",
                    "§7.7 measurements 7 and 8",
                )
            ],
        )

    def test_the_kept_by_pattern_matches_no_removing_setting(self):
        """`Release` and `NDEBUG` are the settings that REMOVE the mechanism.
        A `kept_by` reaching either spares exactly the blocks whose own prose
        names the removal."""
        kept_by = re.compile(removed.REMOVED_MECHANISMS[0].kept_by)

        self.assertEqual(
            [
                text
                for text in (
                    "a Release build defines `NDEBUG`, which removes every `assert()`",
                    "the default build is Release",
                    "-DCMAKE_BUILD_TYPE=Release",
                    "NDEBUG is defined",
                )
                if kept_by.search(text)
            ],
            [],
        )


class EmptyPopulationTest(unittest.TestCase):
    def test_a_document_with_no_task_block_is_a_hard_error(self):
        result = run("neg_removed_empty_population.md")

        self.assertEqual(
            [(f.rule, f.message) for f in result.findings],
            [("no-input", "the removed-mechanism lint examined 0 Check: blocks")],
        )
        self.assertEqual(result.examined, 0)


class RegistryTest(unittest.TestCase):
    def test_a_lint_in_neither_table_raises_at_registration(self):
        with self.assertRaises(cli.LintRegistryError):
            cli.validate_lint_registry(
                all_lints=["removed"], always_run={}, requirements={}
            )

    def test_the_shipped_mappings_account_for_the_lint(self):
        cli.validate_lint_registry()

        self.assertIs(cli.DOCUMENT_LINTS["removed"], removed.run)


if __name__ == "__main__":
    unittest.main()
