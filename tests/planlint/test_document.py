"""Tests for the plan document parser."""

import unittest

from tests.planlint.support import FIXTURES, load_fixture

from planlint import document
from planlint.document import PlanDocument


class TaskBlockParseTest(unittest.TestCase):
    def test_parses_every_task_block_with_identifier_name_and_tier(self):
        doc = load_fixture("clean_plan.md")

        self.assertEqual(
            [(t.ident, t.name, t.tier_text) for t in doc.tasks],
            [
                ("AAA-1", "The build and the surface", "T0"),
                ("AAA-2", "The synthesized corpus", "T0"),
                ("BBB-1", "The gated read", "T1"),
                ("CCC-1", "The conditional extra", "T0"),
                ("CCC-2", "The second conditional", "T0"),
                ("DDD-1", "The Python half", "T0"),
                ("DDD-2", "The oracle comparison", "T2"),
                ("EEE-1", "The late gate", "T0"),
            ],
        )

    def test_task_records_track_number_line_and_section(self):
        doc = load_fixture("clean_plan.md")
        task = doc.task("BBB-1")

        self.assertEqual(
            (task.track, task.number, task.line, task.section),
            ("BBB", 1, 109, "9. The tasks"),
        )

    def test_tier_text_splits_into_a_tier_set(self):
        doc = load_fixture("clean_plan.md")

        self.assertEqual(
            {t.ident: t.tiers for t in doc.tasks},
            {
                "AAA-1": frozenset({"T0"}),
                "AAA-2": frozenset({"T0"}),
                "BBB-1": frozenset({"T1"}),
                "CCC-1": frozenset({"T0"}),
                "CCC-2": frozenset({"T0"}),
                "DDD-1": frozenset({"T0"}),
                "DDD-2": frozenset({"T2"}),
                "EEE-1": frozenset({"T0"}),
            },
        )

    def test_prose_bold_lines_that_open_with_an_identifier_are_not_tasks(self):
        doc = PlanDocument.from_text(
            "**AAA-1 · Real task** — T0\n"
            "Files: `a.cpp`\n"
            "Depends: none\n"
            "Check: `ctest --test-dir build --no-tests=error -R t0_a`\n"
            "\n"
            "**AAA-1 already showed the right answer.** It is prose and not a header.\n",
            name="inline",
        )

        self.assertEqual([t.ident for t in doc.tasks], ["AAA-1"])

    def test_files_design_and_depends_fields_are_captured_verbatim(self):
        doc = load_fixture("clean_plan.md")
        task = doc.task("AAA-1")

        self.assertEqual(
            task.files_text,
            "`tests/CMakeLists.txt`, `tests/t0_alpha.cpp`, "
            "`source/nord/g2/g2Lib/test/CMakeLists.txt`, "
            "`conformance/corpus/*.json`, targets `core_tests`",
        )
        self.assertEqual(task.design_text, "1")
        self.assertEqual(task.depends_text, "none")


class CheckBlockTest(unittest.TestCase):
    def test_check_block_ends_at_the_next_task_header(self):
        doc = load_fixture("clean_plan.md")

        self.assertEqual(
            doc.task("AAA-2").check_text,
            "`ctest --test-dir build --no-tests=error -R t0_beta`. Registered with "
            "`add_test(NAME t0_beta ...)` through the track test list.",
        )

    def test_check_block_ends_at_the_next_markdown_heading(self):
        doc = load_fixture("clean_plan.md")

        self.assertEqual(
            doc.task("CCC-1").check_text,
            "`ctest --test-dir build --no-tests=error -R t0_delta`. Registered with "
            "`add_test(NAME t0_delta ...)`.",
        )

    def test_check_block_spans_several_lines_and_a_table(self):
        doc = PlanDocument.from_text(
            "**AAA-1 · Split check** — T0\n"
            "Files: `t0_one.cpp`, `t1_two.cpp`\n"
            "Depends: none\n"
            "Check: **The check is split by platform.**\n"
            "\n"
            "| Platform | What runs |\n"
            "|---|---|\n"
            "| Linux | `ctest --test-dir build --no-tests=error -R t0_one` |\n"
            "| macOS | `ctest --test-dir build --no-tests=error -R t1_two` |\n"
            "\n"
            "### 2. Next section\n"
            "\n"
            "Prose that quotes `ctest --test-dir build -R t0_not_mine`.\n",
            name="inline",
        )

        block = doc.task("AAA-1").check_text
        self.assertIn("-R t0_one", block)
        self.assertIn("-R t1_two", block)
        self.assertNotIn("t0_not_mine", block)

    def test_a_transcript_fence_inside_a_check_block_is_excluded(self):
        doc = PlanDocument.from_text(
            "**AAA-1 · Counter-example carrier** — T0\n"
            "Files: `t0_one.cpp`\n"
            "Depends: none\n"
            "Check: `ctest --test-dir build --no-tests=error -R t0_one`.\n"
            "The defective form was measured:\n"
            "```\n"
            "$ ctest --test-dir build -R real_test -- --group move\n"
            "CMake Error: Unknown argument: --\n"
            "EXIT=1\n"
            "```\n"
            "That form is forbidden.\n",
            name="inline",
        )

        block = doc.task("AAA-1").check_text
        self.assertIn("-R t0_one", block)
        self.assertNotIn("--group move", block)
        self.assertNotIn("EXIT=1", block)


class LintScopeTest(unittest.TestCase):
    """Section 7.7 states the scope: Check blocks, milestone rows, and every
    fenced block whose first line does NOT open with `$ `."""

    def test_scope_holds_check_blocks_and_milestone_commands(self):
        doc = load_fixture("clean_plan.md")

        self.assertEqual(
            sorted({s.origin for s in doc.scoped_segments()}),
            [
                "check:AAA-1",
                "check:AAA-2",
                "check:BBB-1",
                "check:CCC-1",
                "check:CCC-2",
                "check:DDD-1",
                "check:DDD-2",
                "check:EEE-1",
                "milestone:M1",
            ],
        )

    def test_an_instruction_fence_is_in_scope_and_a_transcript_fence_is_not(self):
        doc = PlanDocument.from_text(
            "## 6. Milestones\n"
            "\n"
            "The check is one command:\n"
            "\n"
            "```\n"
            "cmake -S . -B build && ctest --test-dir build --no-tests=error -R t0_one\n"
            "```\n"
            "\n"
            "It was measured:\n"
            "\n"
            "```\n"
            "$ ctest --test-dir build -R t0_absent\n"
            "EXIT=0\n"
            "```\n",
            name="inline",
        )

        texts = [s.text for s in doc.scoped_segments()]
        self.assertEqual(
            texts,
            [
                "cmake -S . -B build && ctest --test-dir build "
                "--no-tests=error -R t0_one\n"
            ],
        )


class TableTest(unittest.TestCase):
    def test_wave_table_maps_every_task_to_a_wave_label_and_an_order(self):
        doc = load_fixture("clean_plan.md")

        self.assertEqual(
            doc.wave_of,
            {
                "AAA-1": ("1", 1),
                "AAA-2": ("2", 2),
                "BBB-1": ("2", 2),
                "DDD-1": ("2", 2),
                "DDD-2": ("2", 2),
                "CCC-1": ("3", 3),
                "CCC-2": ("3", 3),
                "EEE-1": ("4", 4),
            },
        )

    def test_wave_table_expands_ranges_and_semicolon_groups(self):
        doc = PlanDocument.from_text(
            "### 7.2 The waves\n"
            "\n"
            "| Wave | Order | The tasks in it |\n"
            "|---|---|---|\n"
            "| 3a | 4 | AAA-1 to AAA-3; BBB-2, BBB-4 |\n",
            name="inline",
        )

        self.assertEqual(
            doc.wave_of,
            {
                "AAA-1": ("3a", 4),
                "AAA-2": ("3a", 4),
                "AAA-3": ("3a", 4),
                "BBB-2": ("3a", 4),
                "BBB-4": ("3a", 4),
            },
        )

    def test_conditional_task_table_is_read(self):
        doc = load_fixture("clean_plan.md")

        self.assertEqual(doc.conditional_tasks, {"CCC-1", "CCC-2"})

    def test_repository_table_is_read(self):
        doc = load_fixture("clean_plan.md")

        self.assertEqual(
            doc.repositories,
            {"axiomantic/artifacts": "PRIVATE", "axiomantic/core": "PUBLIC"},
        )

    def test_section_7_4_table_rows_carry_both_ends_the_line_and_the_section(self):
        """Section 7.4's table and section 7.4.1's are ONE table read twice.

        The subsection's header is section 7.4's one column short, and the
        plan states in its own words that the edge it carries is one section
        7.6 assertion 7 counts. A reader that took the six-column form alone
        would report that edge missing from a table the plan deliberately put
        it in.
        """
        doc = load_fixture("clean_plan.md")

        self.assertEqual(
            [(r.source, r.target, r.line, r.section) for r in doc.cross_track_table],
            [
                ("BBB-1", "AAA-2", 62, "7.4 What the graph really says about Wave 2"),
                ("DDD-2", "DDD-1", 63, "7.4 What the graph really says about Wave 2"),
                ("CCC-1", "AAA-2", 64, "7.4 What the graph really says about Wave 2"),
                ("DDD-1", "AAA-2", 73,
                 "7.4.1 Wave 4 is not two independent tracks either"),
            ],
        )

    def test_section_7_4_row_naming_no_bare_identifier_states_no_edge(self):
        """A cell holding prose is not an edge, and a row too short to have a
        TO cell is not one either.

        Without the first guard the reader harvests `the board track` as an
        endpoint; without the second it reads past the end of a short row and
        raises. Both rows are here so that dropping either guard is visible.
        """
        doc = PlanDocument.from_text(
            "### 7.4 What the graph really says\n"
            "\n"
            "| From (track) | Task | To (track) | Task | Kind |\n"
            "|---|---|---|---|---|\n"
            "| sched | SCH-0 | board | the board track | header |\n"
            "| sched | see the note below | board | BRD-0 | header |\n"
            "| sched | SCH-4 | board |\n"
            "| sched | SCH-9 | board | BRD-0 | header |\n",
            name="inline",
        )

        self.assertEqual(
            [(r.source, r.target, r.line) for r in doc.cross_track_table],
            [("SCH-9", "BRD-0", 8)],
        )

    def test_fixture_register_rows_carry_path_owner_repository_and_visibility(self):
        doc = load_fixture("clean_plan.md")

        self.assertEqual(
            [(r.path, r.named_by, r.repository, r.public, r.allow_listed)
             for r in doc.fixture_register],
            [
                ("testdata/synth/", "AAA-2", "core", True, False),
                ("conformance/corpus/*.json", "AAA-1", "core", True, True),
                ("dumps/session.log", "BBB-1", "artifacts", False, False),
            ],
        )


class FixtureIntegrityTest(unittest.TestCase):
    def test_the_fixture_directory_is_not_empty(self):
        self.assertTrue(sorted(FIXTURES.glob("*.md")))


class PathAbbreviationTest(unittest.TestCase):
    """Section 1.1.1 rules B and C.

    The plan writes one file two ways. A lint that compares the strings as
    written reads the two spellings as unrelated paths, so a task can write into
    BRD-0's registrar directory with no declared edge and a clean lint report.
    """

    def test_rule_b_expands_the_three_abbreviated_prefixes(self):
        self.assertEqual(
            document.canonical_path("g2Lib/test/t0_alpha.cpp"),
            "source/nord/g2/g2Lib/test/t0_alpha.cpp",
        )
        self.assertEqual(
            document.canonical_path("g2JucePlugin/g2Device.cpp"),
            "source/nord/g2/g2JucePlugin/g2Device.cpp",
        )
        self.assertEqual(
            document.canonical_path("g2TestConsole/main.cpp"),
            "source/nord/g2/g2TestConsole/main.cpp",
        )

    def test_rule_b_leaves_every_other_path_alone(self):
        for path in ("tests/CMakeLists.txt", "nmg2_tools/pch2.py", "dma.cpp"):
            self.assertEqual(document.canonical_path(path), path)

    def test_an_already_expanded_path_is_idempotent(self):
        """The second call must receive a path that the first call CHANGED.
        A path that was already full makes the second assertion a repeat of the
        first, and thus it cannot fail on its own."""
        once = document.canonical_path("g2Lib/board.h")
        self.assertEqual(once, "source/nord/g2/g2Lib/board.h")
        self.assertEqual(document.canonical_path(once), "source/nord/g2/g2Lib/board.h")

    def test_rule_c_repeats_the_previous_directory(self):
        self.assertEqual(
            document.expand_files_items(["g2Lib/board.h", ".../board.cpp"]),
            ["source/nord/g2/g2Lib/board.h", "source/nord/g2/g2Lib/board.cpp"],
        )

    def test_rule_c_repeats_the_directory_and_never_the_stem(self):
        """`.../cpp` expands to a file literally named `cpp`. The plan carried
        exactly that entry, and it concealed a real collision."""
        self.assertEqual(
            document.expand_files_items(["peripherals56311.h", ".../cpp"]),
            ["peripherals56311.h", ".../cpp"],
        )
        self.assertEqual(
            document.expand_files_items(["a/peripherals56311.h", ".../cpp"]),
            ["a/peripherals56311.h", "a/cpp"],
        )

    def test_an_ellipsis_with_no_previous_directory_is_left_as_written(self):
        """It must fail a path comparison loudly, never resolve to something
        plausible."""
        self.assertEqual(
            document.expand_files_items([".../orphan.cpp"]), [".../orphan.cpp"]
        )

    def test_a_files_line_is_expanded_on_the_task_block(self):
        doc = load_fixture("neg_path_abbreviation.md")
        self.assertIn(
            "source/nord/g2/g2Lib/ellipsed.cpp", doc.task("DDD-1").files_items
        )
        self.assertIn(
            "source/nord/g2/g2Lib/test/t0_short.cpp", doc.task("BBB-1").files_items
        )

    def test_a_directory_owner_row_owns_every_path_beneath_it(self):
        doc = load_fixture("neg_path_abbreviation.md")
        self.assertTrue(
            doc.has_owner("source/nord/g2/g2JucePlugin/covered.cpp")
        )
        self.assertFalse(doc.has_owner("source/nord/g2/g2Lib/shared.cpp"))


class SectionAtTest(unittest.TestCase):
    """The heading a line sits under, by the 1-based line number a `Finding`
    carries. A finding built from a line and not from a task block needs it."""

    def test_a_line_number_yields_the_heading_it_sits_under(self):
        doc = load_fixture("clean_plan.md")

        self.assertEqual(doc.section_at(44), "7.3 The cross-track edges")
        self.assertEqual(doc.section_at(109), "9. The tasks")

    def test_a_line_above_every_heading_sits_under_no_section(self):
        doc = PlanDocument.from_text("preamble\n\n## 1. First\n\nbody\n", name="inline")

        self.assertEqual(doc.section_at(1), "")
        self.assertEqual(doc.section_at(5), "1. First")


class CrossTrackColumnProseTest(unittest.TestCase):
    """Section 7.3's cell is a list of arrow groups and then, often, a
    sentence about them.

    The reader split the cell on `;` alone and then took every identifier after
    the arrow as a target, so a sentence that followed the last group was
    absorbed into it. That invented an edge out of every identifier the
    sentence named, and the invented edges carried the source of a real one, so
    nothing about them looked malformed.

    `planlint.graph` already reads a `Depends:` line this way: edges come from
    the first sentence and an identifier below it is an annotation. The same
    rule is applied here, against the same document.
    """

    def cell(self, text):
        doc = PlanDocument.from_text(
            "### 7.3 Track dependencies\n"
            "\n"
            "| Track | Depends on | Cross-track task edges |\n"
            "|---|---|---|\n"
            f"| chain | sched | {text} |\n",
            name="inline",
        )
        return [(row.source, row.target) for row in doc.cross_track_edges]

    def test_a_sentence_after_an_arrow_group_states_no_edge(self):
        self.assertEqual(
            self.cell(
                "CHN-9 → SCH-15, SCH-19. **CHN-1 reaches BRD-0 through SCH-4**, "
                "which is a declared edge and not a second one."
            ),
            [("CHN-9", "SCH-15"), ("CHN-9", "SCH-19")],
        )

    def test_a_sentence_naming_the_source_states_no_self_loop(self):
        """The absorbed sentence named the cell's own subject, so the reader
        produced an edge from the source to itself. Every cross-track filter
        drops a same-track edge, so the artifact was invisible to the rules
        while sitting in the parsed rows."""
        self.assertEqual(
            self.cell(
                '**CPU-29 → BRD-1.** **THIS CELL READ "none" UNTIL 2026-08-17**: '
                "CPU-29 declares BRD-1 because it writes the memory map."
            ),
            [("CPU-29", "BRD-1")],
        )

    def test_an_em_dash_annotation_states_no_edge(self):
        """The annotation is not always a new sentence.

        Section 7.3's `int` row writes its note after an em dash, INSIDE the
        sentence its last group opens, and the note names that group's own
        source. A reader that cut at the full stop alone still produced the
        self-loop, and every cross-track filter dropped it in silence — the
        same shape as the sentence case, one delimiter further out.
        """
        self.assertEqual(
            self.cell(
                "INT-2 → DSP-14; **INT-3 → SCH-19** — **added 2026-08-19 with "
                "INT-3.** It consumes the `sched` track from the `int` track."
            ),
            [("INT-2", "DSP-14"), ("INT-3", "SCH-19")],
        )

    def test_every_group_in_a_cell_and_every_target_in_a_group_is_read(self):
        self.assertEqual(
            self.cell("REPO-5 → BRD-0; REPO-9 → BRD-0, SCH-0, SCH-18, SCH-19"),
            [
                ("REPO-5", "BRD-0"),
                ("REPO-9", "BRD-0"),
                ("REPO-9", "SCH-0"),
                ("REPO-9", "SCH-18"),
                ("REPO-9", "SCH-19"),
            ],
        )

    def test_a_qualifying_clause_inside_one_sentence_stops_no_target(self):
        """The boundary is the SENTENCE and not the first word that is no
        identifier. Section 7.3's `int` row carries a range, then a clause that
        narrows it, then two more targets; a reader that stopped at `to` or at
        `excluding` would drop what follows."""
        self.assertEqual(
            self.cell(
                "INT-1 → CPU-1 to CPU-25, BRD-1 to BRD-22 excluding the T1 and "
                "conditional members, TOOL-3, TOOL-4"
            ),
            [
                ("INT-1", "CPU-1"),
                ("INT-1", "CPU-25"),
                ("INT-1", "BRD-1"),
                ("INT-1", "BRD-22"),
                ("INT-1", "TOOL-3"),
                ("INT-1", "TOOL-4"),
            ],
        )


class DoneMarkerTest(unittest.TestCase):
    """A completion marker is read wherever it sits in a task body.

    The plan's own section 24.6 records a census taken with a line-anchored
    pattern. Markers written after a `Note: ` lead-in do not satisfy that
    pattern, so the census undercounted and the shortfall presented as a
    measurement. The parser reads the WIDE form and records whether each marker
    satisfies the anchored one, so the next census reads one set and the
    difference between the two is a finding rather than a silence.
    """

    def doc(self, body):
        return PlanDocument.from_text(
            "## 9. The tasks\n"
            "\n"
            "**DSP-2 · The two new DMA request sources** — T0\n"
            "Files: `src/dma.cpp`\n"
            "Depends: none\n"
            "Check: `ctest --test-dir build --no-tests=error -R t0_dma`\n"
            f"{body}\n",
            name="inline",
        )

    def test_a_marker_that_opens_its_line_is_read_and_recorded_anchored(self):
        doc = self.doc("**DONE on 2026-08-06, commit `51903e5c`.**")

        self.assertEqual(
            [(m.task, m.line, m.anchored, m.text) for m in doc.done_markers],
            [("DSP-2", 7, True, "**DONE on 2026-08-06, commit `51903e5c`.**")],
        )

    def test_a_marker_behind_a_lead_in_is_read_and_recorded_unanchored(self):
        doc = self.doc("Note: **DONE on 2026-08-06, commit `51903e5c`.**")

        self.assertEqual(
            [(m.task, m.line, m.anchored, m.text) for m in doc.done_markers],
            [("DSP-2", 7, False, "Note: **DONE on 2026-08-06, commit `51903e5c`.**")],
        )

    def test_a_marker_in_a_table_row_is_no_task_level_marker(self):
        """Section 24.6 row W3-20 states the exclusion and names the case that
        makes it necessary: REPO-15's half-state rows carry a `**DONE` that
        belongs to a half and not to the task."""
        doc = self.doc(
            "| Half | State | Evidence |\n"
            "|---|---|---|\n"
            "| The operator-gated extraction | **DONE** | one commit |"
        )

        self.assertEqual(doc.done_markers, [])

    def test_a_document_with_no_marker_holds_none(self):
        self.assertEqual(load_fixture("clean_plan.md").done_markers, [])


if __name__ == "__main__":
    unittest.main()
