"""Tests for the removed-mechanism lint (section 7.7 measurements 7 and 8).

The calibration is the point of this file. Section 24.6 row W3-4 named six
tasks, row W3-18 re-decided two of them OUT of the class, and that split is a
discriminator proof this project already owned and had not spent. A lint that
flags all six proves nothing. Both directions are asserted here: the positive
fixture must be reported, the negative fixture must be spared, and the negative
fixture is the half that is VERBATIM, because sparing is the direction a wrong
lint fails in.
"""

import ast
import pathlib
import re
import unittest

from tests.planlint.support import load_fixture

from planlint import cli, removed
from planlint.document import PlanDocument

RULE = "check-predicate-removed-by-default-build"

AUTHORITY = (
    "§7.7 measurement 7, TAKEN for `dsp56300`; §7.7 measurement 8, the "
    "`gearmulator` fork transcript, is OWED AND NOT TAKEN, and what binds the "
    "fork until it exists is §7.7's own standing instruction that no `Check:` "
    "there may rest on an assertion"
)

MESSAGE = (
    "a Check: predicate names assert(), which NDEBUG removes from the default "
    "build, so the check reports PASS against a tree in which the property was "
    "never written; the block names no build type that keeps it "
    f"({AUTHORITY})"
)


class AuthorityTest(unittest.TestCase):
    """The cited authority is half owed, and the citation says so.

    §7.7 records of measurement 8 — the `gearmulator` fork transcript — "THIS
    TRANSCRIPT IS OWED AND NOT TAKEN". A field reading "measurements 7 and 8"
    asserted a measured behaviour that has not been measured, which is this
    project's own signature failure wearing the costume of a citation. §7.7's
    instruction for that state is CONSERVATIVE — it forbids resting on an
    assertion in the fork rather than exempting the fork — so the repair is an
    honest citation and not an exemption, and the fork stays in `repositories`.
    """

    def test_the_authority_names_which_measurement_is_taken_and_which_is_owed(self):
        self.assertEqual(removed.REMOVED_MECHANISMS[0].authority, AUTHORITY)

    def test_every_finding_carries_that_authority_in_its_message(self):
        self.assertEqual(
            sorted({f.message for f in run("pos_removed_exclusions.md").findings}),
            [MESSAGE],
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


BOUND = (
    "The registered test drives one case and the bound is held by an "
    "assertion in the helper."
)


class ExclusionFixturePairTest(unittest.TestCase):
    """The aggregate guard over the exclusion pair.

    Every block of the negative fixture went red here during the cycle that
    added its reason, and each per-reason test above names one of them. This
    pair of assertions is what makes a STRAY finding — or a stray sparing —
    fail, which no per-reason test can do on its own.
    """

    def test_the_exclusion_negative_fixture_reports_nothing_over_a_non_zero_population(self):
        result = run("neg_removed_exclusions.md")

        self.assertEqual(result.findings, [])
        self.assertEqual(result.examined, 6)
        self.assertEqual(result.examined_label, "Check: blocks")

    def test_the_exclusion_positive_fixture_reports_every_pair_and_no_other(self):
        result = run("pos_removed_exclusions.md")

        self.assertEqual(
            sorted((f.rule, f.task) for f in result.findings),
            [
                (RULE, "KEP-1"),
                (RULE, "KEP-2"),
                (RULE, "KEP-3"),
                (RULE, "KEP-4"),
                (RULE, "KEP-5"),
                (RULE, "KEP-6"),
            ],
        )
        self.assertEqual(result.examined, 6)


class StruckClauseTest(unittest.TestCase):
    """A `~~`-struck clause is withdrawn text.

    The document's convention is to strike and quote rather than delete, so
    struck text is HISTORY and not a live predicate. A lint that read straight
    through the markers cannot confirm a strike-based repair, which is the form
    every repair in this document takes.
    """

    def test_a_struck_predicate_is_spared(self):
        self.assertEqual(
            [f for f in tuples(run("neg_removed_exclusions.md")) if f[1] == "KEP-1"],
            [],
        )

    def test_the_same_predicate_unstruck_is_reported(self):
        self.assertIn((RULE, "KEP-1", BOUND), tuples(run("pos_removed_exclusions.md")))

    def test_a_live_debug_build_sentence_spares_the_block(self):
        self.assertEqual(
            [f for f in tuples(run("neg_removed_exclusions.md")) if f[1] == "KEP-4"],
            [],
        )

    def test_the_same_block_with_that_sentence_struck_is_reported(self):
        """The other direction, and the reason the strike is applied to
        `kept_by` too: a withdrawn excuse stops excusing."""
        self.assertIn((RULE, "KEP-4", BOUND), tuples(run("pos_removed_exclusions.md")))


class NotTheMechanismTest(unittest.TestCase):
    """A span that carries the mechanism's SPELLING and is provably not it.

    Neither entry narrows `clause_pattern`, which §24.6 row W3-405 refused to
    narrow and row W3-408 restates. Each names a reason the flagged thing
    cannot be a defect of this class, and each reason stands written down with
    no count beside it.
    """

    def test_a_static_assertion_is_spared(self):
        """`NDEBUG` does not remove `static_assert`. It is a compile-time
        construct present in every build type, and the class this lint reads is
        a mechanism the default build REMOVES."""
        self.assertEqual(
            [f for f in tuples(run("neg_removed_exclusions.md")) if f[1] == "KEP-2"],
            [],
        )

    def test_the_same_sentence_without_the_word_static_is_reported(self):
        self.assertIn((RULE, "KEP-2", BOUND), tuples(run("pos_removed_exclusions.md")))

    def test_a_numbered_graph_assertion_citation_is_spared(self):
        """§7.6's assertions are sentences in the plan, checked by `planlint`
        itself, and no build type deletes a sentence."""
        self.assertEqual(
            [f for f in tuples(run("neg_removed_exclusions.md")) if f[1] == "KEP-3"],
            [],
        )

    def test_the_same_sentence_without_the_number_is_reported(self):
        self.assertIn(
            (
                RULE,
                "KEP-3",
                "The registered test drives the row and reports whether the "
                "assertion still holds.",
            ),
            tuples(run("pos_removed_exclusions.md")),
        )

    def test_the_shipped_row_names_each_exclusion_with_its_own_reason(self):
        self.assertEqual(
            [
                (item.name, item.pattern, item.reason)
                for item in removed.REMOVED_MECHANISMS[0].not_the_mechanism
            ],
            [
                (
                    "a static assertion",
                    r"(?i)\bstatic[_\s]assert(?:ion|ions|s)?\b",
                    "NDEBUG does not remove static_assert: it is a compile-time "
                    "construct present in every build type, and this class is a "
                    "mechanism the default build removes",
                ),
                (
                    "a citation of one of the plan's own graph assertions",
                    r"(?i)\bassertions?\s+\d+\b",
                    "a numbered assertion is one of section 7.6's own graph "
                    "invariants, a sentence in this document that planlint "
                    "checks, and no build type deletes a sentence",
                ),
            ],
        )


class RepositoryScopeTest(unittest.TestCase):
    """Section 7.7: the rule "binds each repository from its own transcript".

    The scope is a column on the mechanism ROW and the track-to-repository map
    is read out of the document's own section 7.1 table. Neither is a list in
    `run()`, and the last test here is what holds that shut.
    """

    def test_the_document_reads_the_track_repositories_out_of_its_7_1_table(self):
        self.assertEqual(
            load_fixture("neg_removed_exclusions.md").track_repositories,
            {
                "KEP": ("gearmulator fork",),
                "UNM": ("mcf5307",),
                "SPN": ("gearmulator fork", "nmg2-tools"),
            },
        )

    def test_a_track_placed_in_an_unmeasured_repository_is_spared(self):
        """`mcf5307` is a Nim-driven CMake project whose default build type
        section 7.7 says is NOT measured."""
        self.assertEqual(
            [f for f in tuples(run("neg_removed_exclusions.md")) if f[1] == "UNM-1"],
            [],
        )

    def test_the_same_block_under_a_fork_track_is_reported(self):
        self.assertIn((RULE, "KEP-5", BOUND), tuples(run("pos_removed_exclusions.md")))

    def test_a_track_spanning_a_bound_and_an_unbound_repository_is_spared(self):
        """A block whose track also writes into `nmg2-tools` may be describing
        the work in the repository where `NDEBUG` has no meaning at all."""
        self.assertEqual(
            [f for f in tuples(run("neg_removed_exclusions.md")) if f[1] == "SPN-1"],
            [],
        )

    def test_the_same_block_under_the_single_repository_track_is_reported(self):
        self.assertIn((RULE, "KEP-6", BOUND), tuples(run("pos_removed_exclusions.md")))

    def test_the_shipped_row_names_the_repositories_the_mechanism_binds(self):
        self.assertEqual(
            removed.REMOVED_MECHANISMS[0].repositories,
            ("dsp56300 fork", "gearmulator fork"),
        )

    def test_a_document_that_states_no_track_table_is_not_silently_spared(self):
        """An exclusion must be PROVABLE. A document that states no repository
        for a track proves nothing, and a lint that went quiet whenever the
        table was missing would fail exactly like a lint that is not there."""
        text = (
            "## 9. The tasks\n"
            "\n"
            "**ZZZ-3 · A block in a document with no section 7.1 table** — T0\n"
            "Depends: none\n"
            "Check: `ctest --test-dir build --no-tests=error -R ^t0_zzz$`. " + BOUND + "\n"
        )
        result = removed.run(PlanDocument.from_text(text, name="synthetic"))

        self.assertEqual(
            [(f.rule, f.task, f.evidence) for f in result.findings],
            [(RULE, "ZZZ-3", BOUND)],
        )
        self.assertEqual(result.examined, 1)

    def test_run_states_no_track_and_no_repository(self):
        """The signature defect of this project, refused mechanically. Every
        string `run()` holds is listed here, so a track prefix or a repository
        name appearing in that body fails this test by name."""
        source = pathlib.Path(removed.__file__).read_text(encoding="utf-8")
        body = next(
            node
            for node in ast.parse(source).body
            if isinstance(node, ast.FunctionDef) and node.name == "run"
        )

        self.assertEqual(
            sorted(
                node.value
                for node in ast.walk(body)
                if isinstance(node, ast.Constant) and isinstance(node.value, str)
            ),
            [
                " removes from the default build, so the check reports PASS "
                "against a tree in which the property was never written; the "
                "block names no build type that keeps it (",
                ")",
                ", which ",
                "Check: blocks",
                "a Check: predicate names ",
                "check-predicate-removed-by-default-build",
                "removed",
                "removed-mechanism lint",
            ],
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
            # The invented mechanism has no spelling that is provably not it,
            # and the field is stated rather than defaulted: a row that leaves
            # it out silently claims the same thing without deciding it.
            not_the_mechanism=(),
            # The invented mechanism states no repository scope, so the row
            # excludes nothing on that ground and says so rather than
            # defaulting to it.
            repositories=(),
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
        """The whole row, every column. A field this pin did not name could be
        added, changed or emptied with the suite green."""
        self.assertEqual(
            removed.REMOVED_MECHANISMS,
            (
                removed.RemovedMechanism(
                    mechanism="assert()",
                    clause_pattern=r"(?i)\bassert\(\)|\bassert(?:ion|ions)\b",
                    removed_by="NDEBUG",
                    kept_by=r"(?i)\bdebug\s+build\b|\bdebug-only\b|\bRelWithDebInfo\b"
                    r"|\bCMAKE_BUILD_TYPE\s*=\s*Debug\b",
                    authority=AUTHORITY,
                    not_the_mechanism=(
                        removed.NotTheMechanism(
                            name="a static assertion",
                            pattern=r"(?i)\bstatic[_\s]assert(?:ion|ions|s)?\b",
                            reason=(
                                "NDEBUG does not remove static_assert: it is a "
                                "compile-time construct present in every build "
                                "type, and this class is a mechanism the default "
                                "build removes"
                            ),
                        ),
                        removed.NotTheMechanism(
                            name="a citation of one of the plan's own graph assertions",
                            pattern=r"(?i)\bassertions?\s+\d+\b",
                            reason=(
                                "a numbered assertion is one of section 7.6's own "
                                "graph invariants, a sentence in this document that "
                                "planlint checks, and no build type deletes a "
                                "sentence"
                            ),
                        ),
                    ),
                    repositories=("dsp56300 fork", "gearmulator fork"),
                ),
            ),
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
