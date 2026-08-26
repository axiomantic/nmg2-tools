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
import dataclasses
import pathlib
import re
import unittest

from tests.planlint.support import load_fixture

from planlint import cli, removed
from planlint.document import PlanDocument

RULE = "check-predicate-removed-by-default-build"
SHAPE_RULE = "check-verdict-rests-on-an-assertion-not-firing"

AUTHORITY = (
    "§7.7 measurement 7, TAKEN for `dsp56300`; §7.7 measurement 8, the "
    "`gearmulator` fork transcript, is OWED AND NOT TAKEN, and what binds the "
    "fork until it exists is §7.7's own standing instruction that no `Check:` "
    "there may rest on an assertion"
)

SHAPE_MESSAGE = (
    "a Check: predicate rests its verdict on the not-firing of assert(), which "
    "NDEBUG removes from the default build, so the check reports PASS against a "
    "tree in which the property was never written; the block states none of the "
    "three legal forms that would keep it "
    f"({AUTHORITY})"
)

MESSAGE = (
    "a Check: predicate names assert(), which NDEBUG removes from the default "
    "build, so the check reports PASS against a tree in which the property was "
    "never written; the block states none of the three legal forms that "
    "would keep it "
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
        """Both rules cite it, because §7.7 is the authority for both."""
        self.assertEqual(
            sorted({f.message for f in run("pos_removed_exclusions.md").findings}),
            sorted([MESSAGE, SHAPE_MESSAGE]),
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
        """Five blocks, seven findings. BRD-17 and DSP-7 state the verdict in
        the SHAPE §7.7's boxed rule names as well as in the noun, so each is
        reported under both rules — two true statements about one block, and
        not a duplicate. SCH-28 asserts that an assertion DOES trip, which the
        shape rule does not read: its id says `not-firing` and it means it."""
        result = run("pos_removed_mechanism.md")

        self.assertEqual(
            sorted((f.rule, f.task) for f in result.findings),
            [
                (RULE, "BRD-17"),
                (RULE, "DSP-7"),
                (RULE, "SCH-20"),
                (RULE, "SCH-28"),
                (RULE, "SCH-7"),
                (SHAPE_RULE, "BRD-17"),
                (SHAPE_RULE, "DSP-7"),
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
        self.assertEqual(result.examined, 11)
        self.assertEqual(result.examined_label, "Check: blocks")

    def test_the_exclusion_positive_fixture_reports_every_pair_and_no_other(self):
        result = run("pos_removed_exclusions.md")

        self.assertEqual(
            sorted((f.rule, f.task) for f in result.findings),
            [
                (RULE, "KEP-1"),
                (RULE, "KEP-11"),
                (RULE, "KEP-2"),
                (RULE, "KEP-3"),
                (RULE, "KEP-4"),
                (RULE, "KEP-5"),
                (RULE, "KEP-6"),
                (RULE, "KEP-7"),
                (RULE, "KEP-8"),
                (RULE, "KEP-9"),
                (SHAPE_RULE, "KEP-10"),
            ],
        )
        self.assertEqual(result.examined, 11)


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

    def test_the_prescribed_command_spelling_spares_the_block(self):
        """KEP-4 drives form 1's PROSE wording. This drives the wording §7.7
        itself wrote down — `-DCMAKE_BUILD_TYPE=Debug` on a command inside the
        block — which the shipped pattern refused, because the `-D` puts a word
        character in front of the `C` and a leading `\\b` cannot open there."""
        self.assertEqual(
            [f for f in tuples(run("neg_removed_exclusions.md")) if f[1] == "KEP-11"],
            [],
        )

    def test_the_same_command_naming_the_removing_build_type_is_reported(self):
        """The pair differs by ONE WORD, and it is the word that decides:
        `Release` is the setting that REMOVES the mechanism, so the block that
        names it states no legal form and must still be convicted."""
        self.assertIn((RULE, "KEP-11", BOUND), tuples(run("pos_removed_exclusions.md")))


class KeptByFormTest(unittest.TestCase):
    """§7.7 gives a `Check:` BLOCK that states a debug-only behaviour EXACTLY
    THREE legal forms, and each is a row here with its own name and its own
    reason.

    The lint shipped ONE of the three. A rule that enforces a third of the
    section it cites, and cites the whole section as its authority, convicts
    blocks that did the right thing — which is the sparing side, the direction
    a wrong lint fails in. Both blocks the live document states form 2 in were
    convicted by it.

    This is not the narrowing §24.6 rows W3-405 and W3-408 refused. That
    refusal is about `clause_pattern`, which is untouched. These rows implement
    the other two legal forms OF THE RULE THE LINT ALREADY CLAIMS TO ENFORCE.
    """

    def forms(self):
        return removed.REMOVED_MECHANISMS[0].kept_by

    def test_the_shipped_row_names_each_legal_form_with_its_own_reason(self):
        self.assertEqual(
            [(item.name, item.pattern, item.reason) for item in self.forms()],
            [
                (
                    "form 1 — it names the build type that keeps the mechanism",
                    r"(?i)\bdebug\s+build\b|\bdebug-only\b|\bRelWithDebInfo\b"
                    r"|(?<![A-Za-z0-9_])(?:-D)?CMAKE_BUILD_TYPE\s*=\s*Debug\b",
                    "§7.7: the block \"names `-DCMAKE_BUILD_TYPE=Debug` on a "
                    "command inside the same block\", so the translation unit "
                    "the check reads keeps the mechanism",
                ),
                (
                    "form 2 — it converts the property to an observable read in "
                    "any build type",
                    r"(?i)\b(?:compiled|present|read|readable|available"
                    r"|observable|survives|kept)\b[^.]{0,60}"
                    r"\b(?:in (?:every|any) build type"
                    r"|no build type (?:deletes|removes|strips|omits))\b",
                    "§7.7: the block \"converts the property to an OBSERVABLE "
                    "the check reads in any build type — a returned value, a "
                    "`g2::Status`, a counter, a file\", so no build setting can "
                    "delete the thing the verdict rests on",
                ),
                (
                    "form 3 — it says the property is unchecked in the default "
                    "build and names the task that checks it",
                    r"(?i)\bunchecked in the default build\b[^.]{0,80}"
                    r"\b[A-Z]{2,6}-\d+\b",
                    "§7.7: the block \"says in words that the property is "
                    "unchecked in the default build and names the task that "
                    "checks it\", so the gap is stated rather than left silent, "
                    "and §7.7 says silence is not a fourth form",
                ),
            ],
        )

    def test_no_form_matches_a_removing_setting(self):
        """`Release` and `NDEBUG` are the settings that REMOVE the mechanism.
        A form reaching either spares exactly the blocks whose own prose names
        the removal, and the live document's worst case — DSP-7 — names both in
        the sentence that diagnoses its defect."""
        removing = (
            "a Release build defines `NDEBUG`, which removes every `assert()`",
            "the default build is Release",
            "-DCMAKE_BUILD_TYPE=Release",
            "NDEBUG is defined",
            "the assertion is deleted in every build type that defines NDEBUG",
        )

        self.assertEqual(
            [
                (item.name, text)
                for item in self.forms()
                for text in removing
                if re.search(item.pattern, text)
            ],
            [],
        )

    def test_the_plans_worked_example_is_matched_by_the_build_type_form_alone(self):
        """SCH-18 is §7.7's worked example of correct treatment: it returns a
        `g2::Status` rather than asserting, and its `Check:` reads "in a release
        build as well as a debug build". That sentence is FORM 2 in substance
        and it is form 1 in spelling, and form 1 already shipped — so the
        example was never among the convicted, and this test records which row
        spares it rather than leaving a reader to assume the new one does."""
        sentence = "in a release build as well as a debug build"

        self.assertEqual(
            [item.name for item in self.forms() if re.search(item.pattern, sentence)],
            ["form 1 — it names the build type that keeps the mechanism"],
        )

    def test_form_1_matches_the_spelling_section_7_7_itself_prescribes(self):
        """§7.7 states form 1 in ONE spelling and it carries the `-D`: the
        block *"names `-DCMAKE_BUILD_TYPE=Debug` on a command inside the same
        block"*. Form 1's own `reason` quotes that sentence verbatim, so a
        pattern that does not read it convicts the block that did exactly what
        the rule's own authority prescribes — the sparing-side failure, and in
        the one spelling the section wrote down itself.

        BOTH spellings are driven. The bare one is what a prose sentence
        reaches for and the `-D` one is what a command line carries, and §7.7
        prescribes the second."""
        form1 = self.forms()[0].pattern

        self.assertEqual(
            [
                text
                for text in (
                    "cmake -S . -B build -DCMAKE_BUILD_TYPE=Debug",
                    "-DCMAKE_BUILD_TYPE=Debug",
                    "CMAKE_BUILD_TYPE=Debug",
                    "CMAKE_BUILD_TYPE = Debug",
                )
                if re.search(form1, text)
            ],
            [
                "cmake -S . -B build -DCMAKE_BUILD_TYPE=Debug",
                "-DCMAKE_BUILD_TYPE=Debug",
                "CMAKE_BUILD_TYPE=Debug",
                "CMAKE_BUILD_TYPE = Debug",
            ],
        )

    def test_form_1s_build_type_alternative_reads_no_other_assignment(self):
        """The widening is bounded on the other side in the same test file it
        is made in. `Release` is the setting that REMOVES the mechanism and
        `NDEBUG` is what it defines, so the `-D` prefix may not become a licence
        to read any assignment at all, and a name that merely ENDS in the
        matched one — `EXTRA_CMAKE_BUILD_TYPE` — is a different variable."""
        form1 = self.forms()[0].pattern

        self.assertEqual(
            [
                text
                for text in (
                    "-DCMAKE_BUILD_TYPE=Release",
                    "-DCMAKE_BUILD_TYPE=MinSizeRel",
                    "-DCMAKE_CONFIGURATION_TYPES=Debug",
                    "-DEXTRA_CMAKE_BUILD_TYPE=Debug",
                    "-DNDEBUG",
                )
                if re.search(form1, text)
            ],
            [],
        )


class ObservableFormTest(unittest.TestCase):
    """§7.7's form 2, in both wordings the live document uses.

    BRD-7 records bare `assert()`s REPLACED by a helper "compiled in every
    build type"; DSP-7's live clause reads back the registers "through the
    peripheral set, which is an observable no build type deletes". Both were
    convicted by the shipped rule. Each wording is driven from both directions
    here, because an alternative no fixture reaches is an alternative nothing
    proves.
    """

    def test_the_brd7_wording_spares_the_block(self):
        self.assertEqual(
            [f for f in tuples(run("neg_removed_exclusions.md")) if f[1] == "KEP-7"],
            [],
        )

    def test_the_same_block_without_that_clause_is_reported(self):
        self.assertIn(
            (
                RULE,
                "KEP-7",
                "The registered test drives one case and the bound is held by an "
                "assertion in the helper.",
            ),
            tuples(run("pos_removed_exclusions.md")),
        )

    def test_the_dsp7_wording_spares_the_block(self):
        self.assertEqual(
            [f for f in tuples(run("neg_removed_exclusions.md")) if f[1] == "KEP-8"],
            [],
        )

    def test_the_same_read_back_without_that_clause_is_reported(self):
        self.assertIn(
            (
                RULE,
                "KEP-8",
                "The registered test drives one case and the bound is held by an "
                "assertion in the helper.",
            ),
            tuples(run("pos_removed_exclusions.md")),
        )


class UncheckedFormTest(unittest.TestCase):
    """§7.7's form 3, and the half of it a looser pattern would drop.

    The form has TWO halves — the block "says in words that the property is
    unchecked in the default build" AND "names the task that checks it". The
    paired positive keeps the task identifier and drops the declaration, so the
    pair proves the declaration is what spares and not the identifier beside
    it.
    """

    def test_a_declared_gap_that_names_the_checking_task_spares_the_block(self):
        self.assertEqual(
            [f for f in tuples(run("neg_removed_exclusions.md")) if f[1] == "KEP-9"],
            [],
        )

    def test_a_named_task_with_no_declared_gap_is_reported(self):
        self.assertIn(
            (
                RULE,
                "KEP-9",
                "The registered test drives one case and the bound is held by an "
                "assertion in the helper.",
            ),
            tuples(run("pos_removed_exclusions.md")),
        )

    def test_a_declared_gap_that_names_no_task_is_reported(self):
        """Both halves are required. A block that states the gap and names
        nobody has stated no form at all, and §7.7 says silence is not a fourth
        form."""
        text = (
            "## 9. The tasks\n"
            "\n"
            "**ZZZ-4 · A gap declared and left to nobody** — T0\n"
            "Depends: none\n"
            "Check: `ctest --test-dir build --no-tests=error -R ^t0_zzz$`. " + BOUND + " "
            "The property is unchecked in the default build.\n"
        )
        result = removed.run(PlanDocument.from_text(text, name="synthetic"))

        self.assertEqual(
            [(f.rule, f.task, f.evidence) for f in result.findings],
            [(RULE, "ZZZ-4", BOUND)],
        )


class ShapePredicateTest(unittest.TestCase):
    """The rule keyed on the predicate's SHAPE and not on a noun's spelling.

    §7.7's boxed RULE names one shape: *"No `Check:` line may state its
    predicate as 'an assertion fires' or 'no assertion fires' without naming
    the build type that keeps `assert()`."* The noun-keyed rule reads every
    SPELLING instead, which is a wider question and a different one, and
    §24.6 rows W3-405 and W3-408 refuse to narrow it.

    So this is an ADDITION and not a narrowing. The two rules ask different
    questions of the same block and each says which it asked; a block that
    answers both badly is reported twice, which is two true statements and not
    a duplicate.

    Both rules share the whole sparing side — the strike mask, the
    `not_the_mechanism` rows, the repository scope and §7.7's three legal
    forms — because §7.7 gives those to the block and not to the spelling.
    """

    def test_a_verdict_shape_predicate_with_no_legal_form_is_reported(self):
        self.assertEqual(
            [f for f in tuples(run("pos_removed_exclusions.md")) if f[1] == "KEP-10"],
            [
                (
                    SHAPE_RULE,
                    "KEP-10",
                    "The registered test drives one case and verifies it completes "
                    "without asserting.",
                )
            ],
        )

    def test_the_same_block_under_a_legal_form_is_spared(self):
        self.assertEqual(
            [f for f in tuples(run("neg_removed_exclusions.md")) if f[1] == "KEP-10"],
            [],
        )

    def test_the_shape_finding_carries_its_own_message_and_the_same_authority(self):
        """The message names the SHAPE and not the noun, so a reader can tell
        which of the two questions was asked. The authority is the same, because
        §7.7 is the authority for both."""
        self.assertEqual(
            sorted(
                (f.task, f.severity, f.message)
                for f in run("pos_removed_exclusions.md").findings
                if f.rule == SHAPE_RULE
            ),
            [("KEP-10", "ERROR", SHAPE_MESSAGE)],
        )

    def test_the_shape_pattern_does_not_reach_the_english_noun_alone(self):
        """`without asserting` is the shape; `an assertion in the helper` is the
        noun. KEP-10's positive carries the shape and no noun, and it is
        reported under this rule ALONE — which is what makes the two rules
        separately falsifiable rather than one rule wearing two names."""
        self.assertEqual(
            [
                f[0]
                for f in tuples(run("pos_removed_exclusions.md"))
                if f[1] == "KEP-10"
            ],
            [SHAPE_RULE],
        )

    @staticmethod
    def _shape_block(closing):
        """A block whose predicate is the SHAPE, followed by `closing`.

        `without asserting` carries no noun the wider rule reads, so whatever
        this block reports is the shape rule's answer alone.
        """
        return (
            "## 9. The tasks\n"
            "\n"
            "**ZZZ-7 · A verdict-shape predicate** — T0\n"
            "Depends: none\n"
            "Check: `ctest --test-dir build --no-tests=error -R ^t0_zzz$`. "
            "The registered test drives one case and verifies it completes "
            "without asserting." + closing + "\n"
        )

    def _shape_findings(self, closing):
        result = removed.run(
            PlanDocument.from_text(self._shape_block(closing), name="synthetic")
        )
        return [(f.rule, f.task, f.evidence) for f in result.findings]

    SHAPE_EVIDENCE = (
        "The registered test drives one case and verifies it completes "
        "without asserting."
    )

    def test_a_verdict_shape_predicate_under_form_2_is_spared(self):
        """§7.7 gives its three forms to the BLOCK, so the shape rule answers to
        all three and not to the first. The pair below drops the one sentence,
        which is what makes the sparing attributable to form 2 rather than to
        anything else in the block."""
        self.assertEqual(
            self._shape_findings(
                " The count the verdict reads is a returned value present in "
                "every build type."
            ),
            [],
        )

    def test_a_verdict_shape_predicate_under_form_3_is_spared(self):
        self.assertEqual(
            self._shape_findings(
                " The property is unchecked in the default build, and ZZZ-9 "
                "checks it."
            ),
            [],
        )

    def test_the_same_shape_predicate_with_no_form_at_all_is_reported(self):
        self.assertEqual(
            self._shape_findings(""),
            [(SHAPE_RULE, "ZZZ-7", self.SHAPE_EVIDENCE)],
        )


class PredicateTableTest(unittest.TestCase):
    """Each rule the lint emits is a ROW with its own id, its own message
    fragment and its own severity, and `run()` names none of the three.

    A rule id spelled inside `run()` is the roster defect in its smallest form:
    the body would then know how many rules there are. The AST pin below is what
    holds that shut.
    """

    def test_the_shipped_row_carries_the_two_predicates_the_section_states(self):
        self.assertEqual(
            [
                (item.rule, item.names, item.clause_pattern, item.severity)
                for item in removed.REMOVED_MECHANISMS[0].predicates
            ],
            [
                (
                    RULE,
                    "names",
                    r"(?i)(?<![A-Za-z0-9_])assert[ \t]*\("
                    r"|\bassert(?:ion|ions)\b",
                    "ERROR",
                ),
                (
                    SHAPE_RULE,
                    "rests its verdict on the not-firing of",
                    r"(?i)\bno assertion (?:trips|fires)\b|\bwithout asserting\b"
                    r"|\basserts no assertion\b",
                    "ERROR",
                ),
            ],
        )

    def test_the_noun_predicates_pattern_is_the_one_w3_405_refused_to_narrow(self):
        """The refusal is the point. §24.6 row W3-405 declined to narrow this
        pattern "until the count resembles the roster" and row W3-408 restates
        it. The shape rule is an ADDITION beside it, so this pattern is
        pinned here byte for byte and moves only when that refusal is
        withdrawn."""
        self.assertEqual(
            removed.REMOVED_MECHANISMS[0].predicates[0].clause_pattern,
            r"(?i)(?<![A-Za-z0-9_])assert[ \t]*\(|\bassert(?:ion|ions)\b",
        )


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


class CallSpellingTest(unittest.TestCase):
    r"""The CALL half of the noun predicate, read on its own.

    The alternative shipped as `\bassert\(\)`, which requires LITERAL EMPTY
    PARENTHESES. A C assertion is always written `assert(expr)`, so that
    alternative could not reach one: every live finding the lint reported was
    convicted by the English noun beside it, and the call spelling §7.7's boxed
    rule is actually about had no witness at all. A guard never seen to fire is
    not a guard.

    This WIDENS the call side. It is not the narrowing §24.6 rows W3-405 and
    W3-408 refused: those rows govern the NOUN alternative, which nothing here
    touches and which the pins in `PredicateTableTest` still carry byte for
    byte.

    Each synthetic block below states its spelling and NO English noun, so
    whatever it reports is the call alternative's answer alone.
    """

    # (spelling, does the noun predicate's pattern reach it)
    #
    # The three refusals are the reason the call side needs a LOOKBEHIND rather
    # than `\b`: `\bassert\s*\(` matches inside `static_assert(`, `_Static_assert(`
    # and `g2_assert(`, because `\b` sits between `_` and `a` in none of them —
    # it does not sit there at all, and the match starts at the `assert` the
    # prefix owns. `assert_eq(` is refused by the opposite half: the character
    # after `assert` is `_` and not `(`.
    SPELLINGS = (
        ("assert(status == g2::Status::Ok)", True),
        ("assert (status)", True),
        ("assert()", True),
        ("ASSERT(x)", True),
        ("static_assert(sizeof(Frame) == 64)", False),
        ("_Static_assert(sizeof(Frame) == 64)", False),
        ("g2_assert(x)", False),
        ("assert_eq(a, b)", False),
        ("no assert guards the path", False),
    )

    def test_the_noun_predicates_pattern_answers_each_call_spelling(self):
        pattern = re.compile(
            removed.REMOVED_MECHANISMS[0].predicates[0].clause_pattern
        )

        self.assertEqual(
            [(text, bool(pattern.search(text))) for text, _ in self.SPELLINGS],
            list(self.SPELLINGS),
        )

    @staticmethod
    def _findings(predicate):
        text = (
            "## 9. The tasks\n"
            "\n"
            "**ZZZ-8 · A call-spelling predicate** — T0\n"
            "Depends: none\n"
            "Check: `ctest --test-dir build --no-tests=error -R ^t0_zzz$`. "
            f"{predicate}\n"
        )
        result = removed.run(PlanDocument.from_text(text, name="synthetic"))
        return [(f.rule, f.task, f.evidence) for f in result.findings]

    REAL_CALL = (
        "The registered test drives one case and the code calls "
        "assert(status == g2::Status::Ok) on the result."
    )
    DOCUMENTATION_SPELLING = (
        "The registered test drives one case and the bare assert() in the "
        "helper is what the verdict rests on."
    )
    STATIC = (
        "The registered test drives one case and the code calls "
        "static_assert(sizeof(Frame) == 64) on the type."
    )
    BARE_WORD = "The registered test drives one case and no assert guards the path."

    def test_a_block_whose_only_spelling_is_a_real_call_is_reported(self):
        """The live witness. This is the case the shipped alternative could not
        reach, and it carries no English noun, so the conviction is
        attributable to the call spelling and to nothing else."""
        self.assertEqual(
            self._findings(self.REAL_CALL), [(RULE, "ZZZ-8", self.REAL_CALL)]
        )

    def test_a_block_whose_only_spelling_is_the_documentation_form_is_reported(self):
        """`assert()` with empty parentheses is how prose names the mechanism,
        so widening the call side must not cost this conviction."""
        self.assertEqual(
            self._findings(self.DOCUMENTATION_SPELLING),
            [(RULE, "ZZZ-8", self.DOCUMENTATION_SPELLING)],
        )

    def test_a_block_whose_only_spelling_is_a_static_assertion_is_spared(self):
        """Two mechanisms answer this one: `not_the_mechanism` masks the span,
        and the pattern refuses it unmasked. The spelling test above is the one
        that holds the pattern's half shut, because this test would stay green
        on a pattern that reached inside `static_assert(`."""
        self.assertEqual(self._findings(self.STATIC), [])

    def test_a_block_whose_only_spelling_is_the_bare_word_is_spared(self):
        """`assert` with no parentheses is English, not a call. Nothing masks
        it, so this conviction — or its absence — is the pattern's alone."""
        self.assertEqual(self._findings(self.BARE_WORD), [])


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
                " ",
                " removes from the default build, so the check reports PASS "
                "against a tree in which the property was never written; the "
                "block states none of the three legal forms that would keep it (",
                ")",
                ", which ",
                "Check: blocks",
                "a Check: predicate ",
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
            sorted((f.task, f.rule, f.severity, f.section, f.message) for f in result.findings),
            [
                ("BRD-17", RULE, "ERROR", "9. The tasks", MESSAGE),
                ("BRD-17", SHAPE_RULE, "ERROR", "9. The tasks", SHAPE_MESSAGE),
                ("DSP-7", RULE, "ERROR", "9. The tasks", MESSAGE),
                ("DSP-7", SHAPE_RULE, "ERROR", "9. The tasks", SHAPE_MESSAGE),
                ("SCH-20", RULE, "ERROR", "9. The tasks", MESSAGE),
                ("SCH-28", RULE, "ERROR", "9. The tasks", MESSAGE),
                ("SCH-7", RULE, "ERROR", "9. The tasks", MESSAGE),
            ],
        )

    def test_every_finding_names_the_fixture_line_its_clause_sits_on(self):
        result = run("pos_removed_mechanism.md")

        self.assertEqual(
            sorted((f.task, f.rule, f.line) for f in result.findings),
            [
                ("BRD-17", RULE, 38),
                ("BRD-17", SHAPE_RULE, 38),
                ("DSP-7", RULE, 62),
                ("DSP-7", SHAPE_RULE, 62),
                ("SCH-20", RULE, 50),
                ("SCH-28", RULE, 56),
                ("SCH-7", RULE, 44),
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
        evidence = (
            "The registered test drives one case and asserts that no assertion trips."
        )

        self.assertEqual(
            sorted((f.rule, f.task, f.evidence) for f in self.result().findings),
            [
                (RULE, "ZZZ-2", evidence),
                (SHAPE_RULE, "ZZZ-2", evidence),
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
            predicates=(
                removed.Predicate(
                    rule="check-predicate-removed-by-default-build",
                    names="names",
                    clause_pattern=r"(?i)\bquantum tripwire\b",
                    severity="ERROR",
                ),
            ),
            removed_by="G2_NO_TRIPWIRE",
            kept_by=(
                removed.KeptBy(
                    name="the only form the invented mechanism has",
                    pattern=r"(?i)\btripwire build\b",
                    reason="§0, a passage this project does not carry",
                ),
            ),
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

    def test_a_synthetic_row_reports_at_the_severity_its_predicate_states(self):
        """`severity` is a column and not a constant in `run()`, so this drives
        it to a value neither shipped predicate uses. Both shipped predicates
        are ERROR by decision — `LintResult.failed` is `bool(self.findings)`, so
        a lower severity reorders the report and does not change the exit code,
        which would make the change LOOK like a remediation and deliver none.
        That decision is a value in a row a reader can see and a later pass can
        revisit; without this test the column would be an untested `off`
        switch."""
        table = (
            dataclasses.replace(
                self.SYNTHETIC_TABLE[0],
                predicates=(
                    dataclasses.replace(
                        self.SYNTHETIC_TABLE[0].predicates[0], severity="WARNING"
                    ),
                ),
            ),
        )

        result = removed.run(self.document(), mechanisms=table)

        self.assertEqual(
            [(f.rule, f.task, f.severity) for f in result.findings],
            [("check-predicate-removed-by-default-build", "ZZZ-1", "WARNING")],
        )

    def test_the_shipped_table_carries_the_assert_row_the_plan_states(self):
        """The whole row, every column. A field this pin did not name could be
        added, changed or emptied with the suite green."""
        self.assertEqual(
            removed.REMOVED_MECHANISMS,
            (
                removed.RemovedMechanism(
                    mechanism="assert()",
                    predicates=(
                        removed.Predicate(
                            rule=RULE,
                            names="names",
                            clause_pattern=r"(?i)(?<![A-Za-z0-9_])assert[ \t]*\("
                            r"|\bassert(?:ion|ions)\b",
                            severity="ERROR",
                        ),
                        removed.Predicate(
                            rule=SHAPE_RULE,
                            names="rests its verdict on the not-firing of",
                            clause_pattern=r"(?i)\bno assertion (?:trips|fires)\b"
                            r"|\bwithout asserting\b|\basserts no assertion\b",
                            severity="ERROR",
                        ),
                    ),
                    removed_by="NDEBUG",
                    kept_by=(
                        removed.KeptBy(
                            name="form 1 — it names the build type that keeps the mechanism",
                            pattern=r"(?i)\bdebug\s+build\b|\bdebug-only\b"
                            r"|\bRelWithDebInfo\b"
                            r"|(?<![A-Za-z0-9_])(?:-D)?CMAKE_BUILD_TYPE\s*=\s*Debug\b",
                            reason=(
                                "§7.7: the block \"names `-DCMAKE_BUILD_TYPE=Debug` "
                                "on a command inside the same block\", so the "
                                "translation unit the check reads keeps the mechanism"
                            ),
                        ),
                        removed.KeptBy(
                            name=(
                                "form 2 — it converts the property to an observable "
                                "read in any build type"
                            ),
                            pattern=r"(?i)\b(?:compiled|present|read|readable|available"
                            r"|observable|survives|kept)\b[^.]{0,60}"
                            r"\b(?:in (?:every|any) build type"
                            r"|no build type (?:deletes|removes|strips|omits))\b",
                            reason=(
                                "§7.7: the block \"converts the property to an "
                                "OBSERVABLE the check reads in any build type — a "
                                "returned value, a `g2::Status`, a counter, a file\", "
                                "so no build setting can delete the thing the verdict "
                                "rests on"
                            ),
                        ),
                        removed.KeptBy(
                            name=(
                                "form 3 — it says the property is unchecked in the "
                                "default build and names the task that checks it"
                            ),
                            pattern=r"(?i)\bunchecked in the default build\b[^.]{0,80}"
                            r"\b[A-Z]{2,6}-\d+\b",
                            reason=(
                                "§7.7: the block \"says in words that the property is "
                                "unchecked in the default build and names the task "
                                "that checks it\", so the gap is stated rather than "
                                "left silent, and §7.7 says silence is not a fourth "
                                "form"
                            ),
                        ),
                    ),
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
