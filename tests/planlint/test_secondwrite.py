"""Tests for the second-write lint — all five condition-10 tests of §7.4.2.

Section 7.4.2 states five tests every completion marker must pass, and this
file covers each of them:

  * test 1 — `second-write-no-owner-row`: the document holds no owner row for
    the path the marker names, so the marker's own premise is refuted;
  * test 2 — `second-write-wrong-owner`: the marker's `<OWNER-ID>` is not the
    owner the row names, or the cell names no task block and the comparison is
    ANNOUNCED undecided;
  * test 3 — `second-write-outside-closure`: the owner the marker names is not
    inside the writing task's transitive `Depends:` closure;
  * test 4 — `second-write-outside-class`: the writing task is outside the
    class the owner row states, or the row states no class at all and so
    admits nobody;
  * test 5 — `manifest-without-creator`: no task claims the path BARE.

The five are INDEPENDENT, so a fixture aimed at one is built well-formed in
the other four; where that is impossible the expected list carries every
finding the document really earns.

Tests 2 and 4 have a THIRD shape between them, covered by
`SecondWriteOrderRowTest`: a row whose owner cell states an ORDER — `serial by
wave` — resolves the path by section 7.2's wave table rather than by a named
owner and a prose class. Its owner is the earliest writer, and it admits every
writer whose wave no other writer of the same path holds.

Test 4 cannot read the edit a class describes — "adds a CONDITION to step 2"
is prose. What the lint decides mechanically is the track conjunct: a limb of
the form "every <track>-track task that ..." cannot admit a writer of another
track, whatever the edit. Where admission turns on the edit-kind half, the
finding is `second-write-class-undecided` and never a pass.

The documents here are built inline, on the `test_markers.py` pattern. Each
assertion is a whole-list equality against the complete expected finding, so
an extra finding fails as loudly as a missing one.
"""

import unittest

from planlint import document, secondwrite
from planlint.finding import ERROR, WARNING


def owner_table(rows):
    """A section 7.4.2 owner table carrying the given row texts."""
    body = "".join(rows)
    return (
        "### 7.4.2 Every shared file has one owner\n"
        "\n"
        "| Path | Owner | The mechanism for everybody else |\n"
        "|---|---|---|\n"
        f"{body}"
    )


def repository_owner_table(rows):
    """The four-column shape the plan writes: a Repository column between the
    owner and the mechanism. Section 7.4.2 keys its rows on the (repository,
    path) PAIR, and only this shape carries the first half of that key."""
    body = "".join(rows)
    return (
        "### 7.4.2 Every shared file has one owner\n"
        "\n"
        "| Path | Owner | Repository | The mechanism for everybody else |\n"
        "|---|---|---|---|\n"
        f"{body}"
    )


def bare_owner_table(rows):
    """The two-column shape the clean fixture carries: no mechanism cell."""
    body = "".join(rows)
    return (
        "### 7.4.2 Every shared file has one owner\n"
        "\n"
        "| Path | Owner |\n"
        "|---|---|\n"
        f"{body}"
    )


def task_block(ident, files, line_note="", depends="none"):
    """One task block. `line_note` pads the body so line numbers stay put.

    `depends` is what condition-10 test 3 reads: the owner a marker names must
    sit inside the writing task's transitive `Depends:` closure. A fixture that
    left it at `none` while marking another task's path would fail test 3 as
    well as whatever it meant to test, so every fixture states it.
    """
    return (
        f"**{ident} · A task** — T0\n"
        f"Files: {files}\n"
        f"Depends: {depends}\n"
        "Check: `ctest --test-dir build --no-tests=error -R t0_one`. "
        f"Registered with `add_test(NAME t0_one ...)`.{line_note}\n"
    )


# Section 7.1 is the one home of the track set, and test 4 now resolves a
# class's `<token>-track` through it: the worktree-name column carries the
# track NAME the prose writes and the prefix column carries the identifier
# prefix the writer carries. A document without this table states no tracks,
# so every inline plan here carries it.
TRACK_TABLE = (
    "### 7.1 The tracks\n"
    "\n"
    "| Track | Worktree name | Repository | Task prefix |\n"
    "|---|---|---|---|\n"
    "| 3 | `nmg2-cpu` | `mcf5307` | `CPU` |\n"
    "| 5 | `nmg2-board` | `gearmulator` fork | `BRD` |\n"
    "| 6 | `nmg2-sched` | `gearmulator` fork | `SCH` |\n"
    "| 14 | `nmg2-usbhost` | `mcf5307`, `gearmulator` fork | `USB` |\n"
)


def plan(*sections):
    return document.PlanDocument.from_text(
        TRACK_TABLE + "\n## 9. The tasks\n" + "\n".join(sections),
        name="inline",
    )


def files_line_of(doc, ident):
    """The 1-based line of a task's `Files:` field.

    Every block this file builds puts `Files:` on the line after the header,
    and the lint reports that line; reading it off the parsed task keeps the
    expectation honest if either side moves.
    """
    task = doc.task(ident)
    assert task is not None
    return task.line + 1


def rows(result):
    return [
        (f.rule, f.task, f.line, f.severity, f.message, f.evidence)
        for f in result.findings
    ]


NO_ROW_MESSAGE = (
    "a completion marker asserts that section 7.4.2 holds an owner row for the "
    "(repository, path) pair, and the document holds none; the marker's own "
    "premise is refuted by the document it cites (condition-10 test 1)"
)

CLASSLESS_MESSAGE = (
    "the owner row states no class, so it admits no second writer at all; a "
    "row that names no class grants writes to nobody beyond the owner it "
    "names (condition-10 test 4)"
)

FOREIGN_TRACK_MESSAGE = (
    "every limb of the owner row's class names a track the writing task is "
    "not of, so no limb can admit it whatever edit it describes "
    "(condition-10 test 4)"
)

UNDECIDED_MESSAGE = (
    "whether the writing task is inside the class the owner row states turns "
    "on the edit the class describes, and that description is prose this lint "
    "does not read; reported UNDECIDED rather than passed (condition-10 test 4)"
)

WRONG_OWNER_MESSAGE = (
    "a completion marker asserts that the `<OWNER-ID>` it carries is the owner "
    "section 7.4.2's row names, and the row names another task; a declared "
    "second write against the wrong owner declares nothing (condition-10 "
    "test 2)"
)

OWNER_UNDECIDED_MESSAGE = (
    "the owner row's cell names no task block this tool can resolve, so "
    "whether the marker carries that row's owner turns on prose; reported "
    "UNDECIDED rather than passed (condition-10 test 2)"
)

NO_CREATOR_MESSAGE = (
    "no task claims this path BARE, so the manifest carries declared writers "
    "and no creator; a marked entry is not a claim of ownership, and a "
    "manifest with writers and no creator is a file nobody creates "
    "(condition-10 test 5)"
)

OUTSIDE_CLOSURE_MESSAGE = (
    "the owner the marker names is outside the writing task's transitive "
    "`Depends:` closure, so the path may not exist on the day the write is "
    "declared complete; the edge to the owner is part of the write "
    "(condition-10 test 3)"
)

ORDER_WRONG_OWNER_MESSAGE = (
    "the owner row resolves this path by ORDER rather than by ownership, so "
    "the owner it names is the writer section 7.2 places EARLIEST, and the "
    "`<OWNER-ID>` the marker carries is a later writer (condition-10 test 2)"
)

ORDER_OWNER_UNDECIDED_MESSAGE = (
    "the owner row resolves this path by ORDER, and section 7.2's wave table "
    "places some writer of the path in no row, so the earliest writer — the "
    "owner an order row names — cannot be resolved; reported UNDECIDED rather "
    "than passed (condition-10 test 2)"
)

ORDER_COLLISION_MESSAGE = (
    "the owner row admits a second writer by ORDER, and section 7.2 places "
    "this task in the same wave as another writer of the same path; two "
    "worktrees then hold one file at once, which is the one thing the order "
    "exists to prevent (condition-10 test 4)"
)

ORDER_ADMISSION_UNDECIDED_MESSAGE = (
    "the owner row admits a second writer by ORDER, and section 7.2's wave "
    "table places some writer of the path in no row, so whether two writers "
    "share a wave cannot be decided; reported UNDECIDED rather than passed "
    "(condition-10 test 4)"
)


class SecondWriteWrongOwnerTest(unittest.TestCase):
    """Condition-10 test 2: the marker's `<OWNER-ID>` is the row's owner."""

    ROW = (
        "| `g2Lib/dsp_job.cpp` | **SCH-11**, with **SCH-12** as the one "
        "declared second writer | The class: every sch-track task that adds a "
        "condition to the job body. |\n"
    )

    def test_a_marker_naming_a_second_writer_instead_of_the_owner_is_reported(self):
        """The KNOWN POSITIVE. The row names SCH-11 as owner and SCH-12 as a
        declared second writer, and SCH-34 marks the path `@SCH-12`. The
        marker's premise is that the row names SCH-12 the owner; it does
        not."""
        doc = plan(
            owner_table([self.ROW]),
            task_block("SCH-11", "`g2Lib/dsp_job.cpp`"),
            task_block("SCH-12", "`g2Lib/other.cpp`"),
            task_block(
                "SCH-34", "`g2Lib/dsp_job.cpp@SCH-12`", depends="SCH-12"
            ),
        )
        result = secondwrite.run(doc)
        self.assertEqual(
            rows(result),
            [
                (
                    "second-write-wrong-owner",
                    "SCH-34",
                    files_line_of(doc, "SCH-34"),
                    ERROR,
                    WRONG_OWNER_MESSAGE,
                    "`source/nord/g2/g2Lib/dsp_job.cpp` is marked @SCH-12 by "
                    "SCH-34; section 7.4.2's row names SCH-11 as its owner",
                ),
                (
                    "second-write-class-undecided",
                    "SCH-34",
                    files_line_of(doc, "SCH-34"),
                    WARNING,
                    UNDECIDED_MESSAGE,
                    "`source/nord/g2/g2Lib/dsp_job.cpp` is marked @SCH-12 by "
                    "SCH-34; the row's class reads: SCH-11, with SCH-12 as the "
                    "one declared second writer The class: every sch-track "
                    "task that adds a condition to the job body.",
                ),
            ],
        )

    def test_a_marker_naming_the_rows_own_owner_raises_no_test_2_finding(self):
        doc = plan(
            owner_table([self.ROW]),
            task_block("SCH-11", "`g2Lib/dsp_job.cpp`"),
            task_block(
                "SCH-34", "`g2Lib/dsp_job.cpp@SCH-11`", depends="SCH-11"
            ),
        )
        result = secondwrite.run(doc)
        self.assertEqual(
            [r for r in rows(result) if r[0] == "second-write-wrong-owner"],
            [],
        )

    def test_an_unresolvable_owner_cell_is_undecided_never_passed(self):
        """`the operator` and `the plugin track` are owner cells section 7.4.2
        really carries. Neither names a task block, so test 2 cannot be
        decided — and a silence here reads exactly like an adjudication."""
        doc = plan(
            owner_table(
                [
                    "| `g2Lib/dsp_job.cpp` | **the operator** | The class: "
                    "every sch-track task that adds a condition. |\n"
                ]
            ),
            task_block("SCH-11", "`g2Lib/dsp_job.cpp`"),
            task_block(
                "SCH-34", "`g2Lib/dsp_job.cpp@SCH-11`", depends="SCH-11"
            ),
        )
        result = secondwrite.run(doc)
        self.assertEqual(
            [r for r in rows(result) if r[0].startswith("second-write-owner")],
            [
                (
                    "second-write-owner-undecided",
                    "SCH-34",
                    files_line_of(doc, "SCH-34"),
                    WARNING,
                    OWNER_UNDECIDED_MESSAGE,
                    "`source/nord/g2/g2Lib/dsp_job.cpp` is marked @SCH-11 by "
                    "SCH-34; the owner cell reads: the operator",
                )
            ],
        )

    def test_a_path_with_no_owner_row_raises_no_test_2_finding(self):
        """Test 1 already reports the missing row. Test 2 reads that row, so
        with no row there is nothing for it to compare and it says nothing —
        the row's absence is one defect and not two."""
        doc = plan(
            owner_table([]),
            task_block("SCH-11", "`g2Lib/dsp_job.cpp`"),
            task_block(
                "SCH-34", "`g2Lib/dsp_job.cpp@SCH-11`", depends="SCH-11"
            ),
        )
        result = secondwrite.run(doc)
        self.assertEqual(
            [r[0] for r in rows(result)],
            ["second-write-no-owner-row"],
        )


class ManifestWithoutCreatorTest(unittest.TestCase):
    """Condition-10 test 5: some task claims the path BARE.

    Section 7.4.2 states the defect this exists for by name — the
    `conformance/CMakeLists.txt` gap CPU-26 closed — and section 7.6 assertion
    8 restates it: "A path with marked writers and no bare claimant is a
    FAILURE, because a manifest with writers and no creator is" that gap.
    """

    ROW = (
        "| `g2Lib/test/tests_sched.cmake` | **SCH-0** | The class: every "
        "sch-track task that registers its own name. |\n"
    )

    def test_a_path_every_writer_marks_has_no_creator_and_is_reported(self):
        """The KNOWN POSITIVE. Two tasks declare second writes into the list
        and no task's `Files:` line claims it bare, so nothing creates it."""
        doc = plan(
            owner_table([self.ROW]),
            task_block("SCH-0", "`g2Lib/test/other.cmake`"),
            task_block(
                "SCH-30",
                "`g2Lib/test/tests_sched.cmake@SCH-0`",
                depends="SCH-0",
            ),
            task_block(
                "SCH-31",
                "`g2Lib/test/tests_sched.cmake@SCH-0`",
                depends="SCH-0",
            ),
        )
        result = secondwrite.run(doc)
        self.assertEqual(
            [r for r in rows(result) if r[0] == "manifest-without-creator"],
            [
                (
                    "manifest-without-creator",
                    "SCH-30",
                    files_line_of(doc, "SCH-30"),
                    ERROR,
                    NO_CREATOR_MESSAGE,
                    "`source/nord/g2/g2Lib/test/tests_sched.cmake` is marked "
                    "@SCH-0 by SCH-30, and no task's `Files:` line claims it "
                    "bare",
                ),
                (
                    "manifest-without-creator",
                    "SCH-31",
                    files_line_of(doc, "SCH-31"),
                    ERROR,
                    NO_CREATOR_MESSAGE,
                    "`source/nord/g2/g2Lib/test/tests_sched.cmake` is marked "
                    "@SCH-0 by SCH-31, and no task's `Files:` line claims it "
                    "bare",
                ),
            ],
        )

    def test_a_bare_claim_anywhere_in_the_document_satisfies_the_test(self):
        doc = plan(
            owner_table([self.ROW]),
            task_block("SCH-0", "`g2Lib/test/tests_sched.cmake`"),
            task_block(
                "SCH-30",
                "`g2Lib/test/tests_sched.cmake@SCH-0`",
                depends="SCH-0",
            ),
        )
        result = secondwrite.run(doc)
        self.assertEqual(
            [r for r in rows(result) if r[0] == "manifest-without-creator"],
            [],
        )

    def test_a_bare_claim_in_the_ABBREVIATED_spelling_still_counts(self):
        """Rules B and C make `g2Lib/...` and `source/nord/g2/g2Lib/...` one
        spelling. A creator that writes the short form creates the same file,
        and a comparison of raw strings would report it missing."""
        doc = plan(
            owner_table([self.ROW]),
            task_block("SCH-0", "`g2Lib/test/tests_sched.cmake`"),
            task_block(
                "SCH-30",
                "`source/nord/g2/g2Lib/test/tests_sched.cmake@SCH-0`",
                depends="SCH-0",
            ),
        )
        result = secondwrite.run(doc)
        self.assertEqual(
            [r for r in rows(result) if r[0] == "manifest-without-creator"],
            [],
        )

    def test_a_second_marked_writer_is_not_a_creator(self):
        """A marked entry is not a claim — section 1.1.1 rule D. Counting one
        would let a file with two declared writers and no creator pass, which
        is the exact defect this test exists for."""
        doc = plan(
            owner_table([self.ROW]),
            task_block(
                "SCH-0", "`g2Lib/test/tests_sched.cmake@SCH-0`"
            ),
            task_block(
                "SCH-30",
                "`g2Lib/test/tests_sched.cmake@SCH-0`",
                depends="SCH-0",
            ),
        )
        result = secondwrite.run(doc)
        self.assertEqual(
            [(r[0], r[1]) for r in rows(result) if r[0] == "manifest-without-creator"],
            [
                ("manifest-without-creator", "SCH-0"),
                ("manifest-without-creator", "SCH-30"),
            ],
        )

    def test_a_path_with_no_owner_row_is_still_held_against_test_5(self):
        """Test 5 reads the `Files:` lines and not the row, so a missing row
        does not excuse a missing creator. Both stand."""
        doc = plan(
            owner_table([]),
            task_block("SCH-0", "`g2Lib/test/other.cmake`"),
            task_block(
                "SCH-30",
                "`g2Lib/test/tests_sched.cmake@SCH-0`",
                depends="SCH-0",
            ),
        )
        result = secondwrite.run(doc)
        self.assertEqual(
            [r[0] for r in rows(result)],
            ["second-write-no-owner-row", "manifest-without-creator"],
        )

    def test_the_bare_claim_set_is_computed_from_unmarked_entries_only(self):
        doc = plan(
            owner_table([self.ROW]),
            task_block("SCH-0", "`g2Lib/a.cmake`, `g2Lib/b.cmake@SCH-9`"),
        )
        self.assertEqual(
            secondwrite.bare_claims(doc),
            {document.canonical_path("g2Lib/a.cmake")},
        )

    def test_a_bare_claim_of_the_containing_DIRECTORY_creates_the_path(self):
        """A bare claim of a `/`-suffixed path claims every path beneath it.

        REPO-14 claims `planlint/` and `tests/planlint/` bare and section
        7.4.2's own row for the pair says a `/`-suffixed row owns every path
        beneath it. `owner_cell` already resolves a path to its directory row,
        so test 1 found the owner through the directory claim and stayed
        silent while test 5 missed the CREATOR through the identical claim and
        fired. One entry, two tests, opposite readings of one `/`.
        """
        doc = plan(
            owner_table([self.ROW]),
            task_block("SCH-0", "`g2Lib/test/`"),
            task_block(
                "SCH-30",
                "`g2Lib/test/tests_sched.cmake@SCH-0`",
                depends="SCH-0",
            ),
        )
        result = secondwrite.run(doc)
        self.assertEqual(
            rows(result),
            [
                (
                    "second-write-class-undecided",
                    "SCH-30",
                    files_line_of(doc, "SCH-30"),
                    WARNING,
                    UNDECIDED_MESSAGE,
                    "`source/nord/g2/g2Lib/test/tests_sched.cmake` is marked "
                    "@SCH-0 by SCH-30; the row's class reads: SCH-0 The class: "
                    "every sch-track task that registers its own name.",
                )
            ],
        )

    def test_a_bare_directory_claim_covers_only_the_paths_beneath_it(self):
        """The KNOWN NEGATIVE for the directory rule. A claim of a directory
        the marked path does not sit under creates nothing, and a rule that
        read any `/`-suffixed claim as covering would clear this too."""
        doc = plan(
            owner_table([self.ROW]),
            task_block("SCH-0", "`g2Lib/other/`"),
            task_block(
                "SCH-30",
                "`g2Lib/test/tests_sched.cmake@SCH-0`",
                depends="SCH-0",
            ),
        )
        result = secondwrite.run(doc)
        self.assertEqual(
            [r for r in rows(result) if r[0] == "manifest-without-creator"],
            [
                (
                    "manifest-without-creator",
                    "SCH-30",
                    files_line_of(doc, "SCH-30"),
                    ERROR,
                    NO_CREATOR_MESSAGE,
                    "`source/nord/g2/g2Lib/test/tests_sched.cmake` is marked "
                    "@SCH-0 by SCH-30, and no task's `Files:` line claims it "
                    "bare",
                )
            ],
        )


class BareClaimResolutionTest(unittest.TestCase):
    """The claim-set lookup, held directly: exact match, then a `/`-suffixed
    prefix — the same rule `owner_cell` states for owner rows."""

    CLAIMED = frozenset({"planlint/", "tests/planlint/", "nmg2_tools/cli.py"})

    def test_an_exact_claim_covers_its_own_path(self):
        self.assertTrue(
            secondwrite.claimed_bare("nmg2_tools/cli.py", self.CLAIMED)
        )

    def test_a_directory_claim_covers_a_path_beneath_it(self):
        self.assertTrue(
            secondwrite.claimed_bare("planlint/removed.py", self.CLAIMED)
        )

    def test_a_directory_claim_covers_a_path_nested_deeper(self):
        self.assertTrue(
            secondwrite.claimed_bare(
                "tests/planlint/fixtures/pos_removed_mechanism.md", self.CLAIMED
            )
        )

    def test_a_path_under_no_claim_is_uncovered(self):
        self.assertFalse(
            secondwrite.claimed_bare("nmg2_tools/sigscan.py", self.CLAIMED)
        )

    def test_a_claim_that_is_a_string_prefix_and_not_a_directory_covers_nothing(self):
        """`planlint` without the `/` is a FILE claim, and `planlintx.py`
        is not beneath it. A `startswith` over the raw set reads both wrong."""
        self.assertFalse(secondwrite.claimed_bare("planlintx.py", frozenset({"planlint"})))


class SecondWriteOutsideClosureTest(unittest.TestCase):
    """Condition-10 test 3: the marked owner is inside the writer's closure.

    Section 7.4.2 states where the edge lives: "a task that must write a path
    another task owns adds that owner to its OWN `Depends:` line, and that edge
    is part of the write." The test is therefore fully mechanical — a
    transitive reachability question over the declared `Depends:` graph — and
    nothing about it turns on prose.
    """

    ROW = (
        "| `g2Lib/dsp_job.cpp` | **SCH-11** | The class: every sch-track task "
        "that adds a condition to the job body. |\n"
    )

    def test_a_marker_whose_owner_the_writer_does_not_wait_on_is_reported(self):
        """The KNOWN POSITIVE. SCH-34 declares the second write and depends on
        nothing, so on the day it is declared complete the file it writes may
        not exist."""
        doc = plan(
            owner_table([self.ROW]),
            task_block("SCH-11", "`g2Lib/dsp_job.cpp`"),
            task_block("SCH-34", "`g2Lib/dsp_job.cpp@SCH-11`", depends="none"),
        )
        result = secondwrite.run(doc)
        self.assertEqual(
            [r for r in rows(result) if r[0] == "second-write-outside-closure"],
            [
                (
                    "second-write-outside-closure",
                    "SCH-34",
                    files_line_of(doc, "SCH-34"),
                    ERROR,
                    OUTSIDE_CLOSURE_MESSAGE,
                    "`source/nord/g2/g2Lib/dsp_job.cpp` is marked @SCH-11 by "
                    "SCH-34, whose dependency closure is {SCH-34}",
                )
            ],
        )

    def test_a_directly_declared_owner_is_inside_the_closure(self):
        doc = plan(
            owner_table([self.ROW]),
            task_block("SCH-11", "`g2Lib/dsp_job.cpp`"),
            task_block(
                "SCH-34", "`g2Lib/dsp_job.cpp@SCH-11`", depends="SCH-11"
            ),
        )
        result = secondwrite.run(doc)
        self.assertEqual(
            [r for r in rows(result) if r[0] == "second-write-outside-closure"],
            [],
        )

    def test_a_transitively_reached_owner_is_inside_the_closure(self):
        """The closure is TRANSITIVE, and section 7.4.2 says a reader will
        find it wider than the writing task's own subject explains."""
        doc = plan(
            owner_table([self.ROW]),
            task_block("SCH-11", "`g2Lib/dsp_job.cpp`"),
            task_block("SCH-20", "`g2Lib/mid.cpp`", depends="SCH-11"),
            task_block(
                "SCH-34", "`g2Lib/dsp_job.cpp@SCH-11`", depends="SCH-20"
            ),
        )
        result = secondwrite.run(doc)
        self.assertEqual(
            [r for r in rows(result) if r[0] == "second-write-outside-closure"],
            [],
        )

    def test_a_marker_naming_no_task_block_at_all_is_outside_the_closure(self):
        """A closure holds task blocks. An owner id that names none is not in
        it, and the evidence says which of the two shapes it is rather than
        leaving a reader to guess at a missing edge."""
        doc = plan(
            owner_table([self.ROW]),
            task_block("SCH-11", "`g2Lib/dsp_job.cpp`"),
            task_block(
                "SCH-34", "`g2Lib/dsp_job.cpp@SCH-99`", depends="SCH-11"
            ),
        )
        result = secondwrite.run(doc)
        self.assertEqual(
            [r for r in rows(result) if r[0] == "second-write-outside-closure"],
            [
                (
                    "second-write-outside-closure",
                    "SCH-34",
                    files_line_of(doc, "SCH-34"),
                    ERROR,
                    OUTSIDE_CLOSURE_MESSAGE,
                    "`source/nord/g2/g2Lib/dsp_job.cpp` is marked @SCH-99 by "
                    "SCH-34, and SCH-99 is no task block of this document",
                )
            ],
        )

    def test_the_owner_writing_its_own_path_is_inside_its_own_closure(self):
        doc = plan(
            owner_table([self.ROW]),
            task_block("SCH-11", "`g2Lib/dsp_job.cpp@SCH-11`"),
        )
        result = secondwrite.run(doc)
        self.assertEqual(
            [r for r in rows(result) if r[0] == "second-write-outside-closure"],
            [],
        )

    def test_a_path_with_no_owner_row_is_still_held_against_the_closure(self):
        """Test 3 reads the MARKER, not the row, so a missing row does not
        excuse it. Both findings stand: the row is absent AND the edge is."""
        doc = plan(
            owner_table([]),
            task_block("SCH-11", "`g2Lib/dsp_job.cpp`"),
            task_block("SCH-34", "`g2Lib/dsp_job.cpp@SCH-11`", depends="none"),
        )
        result = secondwrite.run(doc)
        self.assertEqual(
            [r[0] for r in rows(result)],
            ["second-write-no-owner-row", "second-write-outside-closure"],
        )


class SecondWriteNoOwnerRowTest(unittest.TestCase):
    """Condition-10 test 1: the owner row the marker asserts must exist."""

    def test_a_marker_whose_path_has_no_owner_row_is_reported(self):
        doc = plan(
            task_block("SCH-9", "`g2Lib/esai_frame.h`"),
            task_block(
                "SCH-10", "`g2Lib/esai_frame.h@SCH-9`", depends="SCH-9"
            ),
        )
        result = secondwrite.run(doc)
        self.assertEqual(
            rows(result),
            [
                (
                    "second-write-no-owner-row",
                    "SCH-10",
                    files_line_of(doc, "SCH-10"),
                    ERROR,
                    NO_ROW_MESSAGE,
                    "`source/nord/g2/g2Lib/esai_frame.h` is marked @SCH-9 by "
                    "SCH-10; section 7.4.2 holds no owner row for it",
                )
            ],
        )

    def test_an_abbreviated_marker_resolves_through_rules_b_and_c(self):
        """The marker rides on the EXPANDED path. `g2Lib/...` and
        `source/nord/g2/g2Lib/...` are one spelling by rule B, so a row keyed
        on the long form must satisfy the short one and conversely."""
        doc = plan(
            owner_table(["| `source/nord/g2/g2Lib/rowed.cpp` | **AAA-1** | asks AAA-1. |\n"]),
            task_block("AAA-2", "`g2Lib/rowed.cpp@AAA-1`"),
        )
        result = secondwrite.run(doc)
        self.assertEqual(
            [r for r in rows(result) if r[0] == "second-write-no-owner-row"],
            [],
        )

    def test_a_directory_row_owns_the_marked_path_beneath_it(self):
        doc = plan(
            owner_table(["| `g2Lib/test/` | **AAA-1** | asks AAA-1. |\n"]),
            task_block("AAA-2", "`g2Lib/test/new_case.cpp@AAA-1`"),
        )
        result = secondwrite.run(doc)
        self.assertEqual(
            [r for r in rows(result) if r[0] == "second-write-no-owner-row"],
            [],
        )

    def test_a_bare_entry_is_neither_examined_nor_reported(self):
        """Only MARKED entries are second writes. A bare claim is ownership,
        which `shared-path-without-owner` governs, not this lint."""
        doc = plan(
            owner_table([]),
            task_block("AAA-1", "`g2Lib/mine.cpp`"),
        )
        result = secondwrite.run(doc)
        self.assertEqual(rows(result), [])


class SecondWriteOutsideClassTest(unittest.TestCase):
    """Condition-10 test 4: the writer is inside the class the row states."""

    def test_a_classless_row_refuses_a_second_writer(self):
        doc = plan(
            owner_table(["| `g2Lib/dsp_job.cpp` | **SCH-11** | Ask SCH-11. |\n"]),
            task_block("SCH-11", "`g2Lib/dsp_job.cpp`"),
            task_block(
                "SCH-34", "`g2Lib/dsp_job.cpp@SCH-11`", depends="SCH-11"
            ),
        )
        result = secondwrite.run(doc)
        self.assertEqual(
            rows(result),
            [
                (
                    "second-write-outside-class",
                    "SCH-34",
                    files_line_of(doc, "SCH-34"),
                    ERROR,
                    CLASSLESS_MESSAGE,
                    "`source/nord/g2/g2Lib/dsp_job.cpp` is marked @SCH-11 by SCH-34; the owner "
                    "row names SCH-11 and states no class",
                )
            ],
        )

    def test_a_two_column_row_states_no_mechanism_and_is_undecided(self):
        """A two-column table states no mechanism COLUMN at all, so no class
        is stated anywhere and nothing was refused. That is the undecided
        branch, and the undecided identity is what reports it."""
        doc = plan(
            bare_owner_table(["| `g2Lib/dsp_job.cpp` | **SCH-11** |\n"]),
            task_block("SCH-11", "`g2Lib/dsp_job.cpp`"),
            task_block(
                "SCH-34", "`g2Lib/dsp_job.cpp@SCH-11`", depends="SCH-11"
            ),
        )
        result = secondwrite.run(doc)
        self.assertEqual(
            [(r[0], r[3]) for r in rows(result)],
            [("second-write-class-undecided", WARNING)],
        )

    def test_the_rows_own_writer_is_not_a_second_writer(self):
        """The owner writes by ownership, not by class membership. Demanding
        that the owner sit inside its own class is a category error.

        Test 5 still speaks, and truthfully: this document's only entry for
        the path is MARKED, so nothing creates the file. That finding is the
        whole of what the classless row produces here, and no test-4 finding
        stands beside it."""
        doc = plan(
            owner_table(["| `g2Lib/dsp_job.cpp` | **SCH-11** | Ask SCH-11. |\n"]),
            task_block("SCH-11", "`g2Lib/dsp_job.cpp@SCH-11`"),
        )
        result = secondwrite.run(doc)
        self.assertEqual(
            [(r[0], r[1], r[3]) for r in rows(result)],
            [("manifest-without-creator", "SCH-11", ERROR)],
        )

    def test_a_writer_outside_every_named_track_is_outside_the_class(self):
        doc = plan(
            owner_table(
                [
                    "| `g2Lib/dsp_job.cpp` | **SCH-11** | The class of second "
                    "writer: every sch-track task that adds a condition to the "
                    "job body. |\n"
                ]
            ),
            task_block("SCH-11", "`g2Lib/dsp_job.cpp`"),
            task_block(
                "BRD-4", "`g2Lib/dsp_job.cpp@SCH-11`", depends="SCH-11"
            ),
        )
        result = secondwrite.run(doc)
        self.assertEqual(
            rows(result),
            [
                (
                    "second-write-outside-class",
                    "BRD-4",
                    files_line_of(doc, "BRD-4"),
                    ERROR,
                    FOREIGN_TRACK_MESSAGE,
                    "`source/nord/g2/g2Lib/dsp_job.cpp` is marked @SCH-11 by BRD-4 of track "
                    "brd; the row's class names tracks: sch",
                )
            ],
        )

    def test_a_track_match_leaves_the_edit_kind_undecided_not_passed(self):
        """The class names the writer's track, so the track conjunct admits
        it; whether the EDIT matches is prose. That branch is reported
        UNDECIDED under its own rule and never silently passed."""
        doc = plan(
            owner_table(
                [
                    "| `g2Lib/dsp_job.cpp` | **SCH-11** | The class of second "
                    "writer: every sch-track task that adds a condition to the "
                    "job body. |\n"
                ]
            ),
            task_block("SCH-11", "`g2Lib/dsp_job.cpp`"),
            task_block(
                "SCH-34", "`g2Lib/dsp_job.cpp@SCH-11`", depends="SCH-11"
            ),
        )
        result = secondwrite.run(doc)
        self.assertEqual(
            rows(result),
            [
                (
                    "second-write-class-undecided",
                    "SCH-34",
                    files_line_of(doc, "SCH-34"),
                    WARNING,
                    UNDECIDED_MESSAGE,
                    "`source/nord/g2/g2Lib/dsp_job.cpp` is marked @SCH-11 by SCH-34; the "
                    "row's class reads: SCH-11 The class of second writer: every "
                    "sch-track task that adds a condition to the job body.",
                )
            ],
        )

    def test_a_longer_prose_track_token_still_covers_the_identifier(self):
        """`usbhost-track` covers a `USB-` writer and `sched-track` covers a
        `SCH-` writer by prefix. Exact equality only would report every such
        writer outside its own class, and a rule that fires on correct input
        trains a reader to ignore it."""
        doc = plan(
            owner_table(
                [
                    "| `source/nord/g2/g2UsbHost/list.cmake` | **USB-0** | The "
                    "class: every usbhost-track task that registers its own "
                    "test. |\n"
                ]
            ),
            task_block("USB-0", "`source/nord/g2/g2UsbHost/list.cmake`"),
            task_block(
                "USB-3",
                "`source/nord/g2/g2UsbHost/list.cmake@USB-0`",
                depends="USB-0",
            ),
        )
        result = secondwrite.run(doc)
        self.assertEqual(
            [r[0] for r in rows(result)],
            ["second-write-class-undecided"],
        )

    def test_a_class_with_no_track_limb_cannot_exclude_any_writer(self):
        """`(a) every task that grows the published contract` names no track.
        No track conjunct exists to fail, so exclusion is not decidable and
        the finding is the undecided one, for any writer."""
        doc = plan(
            owner_table(
                [
                    "| `include/mcf5307.h` | **CPU-0** | The CLASS of second "
                    "writers, in TWO limbs: (a) every task that grows the "
                    "published contract; (b) every task that documents the "
                    "re-entrancy contract. |\n"
                ]
            ),
            task_block("CPU-0", "`include/mcf5307.h`"),
            task_block("BRD-2", "`include/mcf5307.h@CPU-0`", depends="CPU-0"),
        )
        result = secondwrite.run(doc)
        self.assertEqual(
            [r[0] for r in rows(result)],
            ["second-write-class-undecided"],
        )


class ClassIsReadFromTheWholeRowTest(unittest.TestCase):
    """Section 7.4.2 states no rule that the class must sit in one column.

    The ten `tests_<track>.cmake` rows write the class sentence in the OWNER
    cell and spend the mechanism cell on WHY the row replaced a per-list
    roster. A reader of the mechanism cell alone reports "states no class"
    about a row whose first sentence states the class.
    """

    OWNER_CELL_CLASS = (
        "SCH-0 creates it EMPTY. The owning track fills it. The CLASS of "
        "second writers is: every sched-track task whose Check: passes a name "
        "to ctest -R against a test source in g2Lib/test/."
    )
    WHY_MECHANISM = (
        "This row replaced a per-list roster, because a roster is amended once "
        "per writer and a class is not."
    )

    def test_a_class_in_the_owner_cell_is_read_and_the_row_is_not_classless(self):
        doc = plan(
            owner_table(
                [
                    f"| `g2Lib/test/tests_sched.cmake` | **{self.OWNER_CELL_CLASS}** "
                    f"| {self.WHY_MECHANISM} |\n"
                ]
            ),
            task_block("SCH-0", "`g2Lib/test/tests_sched.cmake`"),
            task_block(
                "SCH-30",
                "`g2Lib/test/tests_sched.cmake@SCH-0`",
                depends="SCH-0",
            ),
        )
        result = secondwrite.run(doc)
        self.assertEqual(
            rows(result),
            [
                (
                    "second-write-class-undecided",
                    "SCH-30",
                    files_line_of(doc, "SCH-30"),
                    WARNING,
                    UNDECIDED_MESSAGE,
                    "`source/nord/g2/g2Lib/test/tests_sched.cmake` is marked "
                    "@SCH-0 by SCH-30; the row's class reads: "
                    f"{self.OWNER_CELL_CLASS} {self.WHY_MECHANISM}",
                )
            ],
        )

    def test_a_track_limb_in_the_owner_cell_excludes_a_foreign_writer(self):
        """The track conjunct is read from the same row text the class is,
        or a class stated in the owner cell would admit every track."""
        doc = plan(
            owner_table(
                [
                    f"| `g2Lib/test/tests_sched.cmake` | **{self.OWNER_CELL_CLASS}** "
                    f"| {self.WHY_MECHANISM} |\n"
                ]
            ),
            task_block("SCH-0", "`g2Lib/test/tests_sched.cmake`"),
            task_block(
                "BRD-4",
                "`g2Lib/test/tests_sched.cmake@SCH-0`",
                depends="SCH-0",
            ),
        )
        result = secondwrite.run(doc)
        self.assertEqual(
            rows(result),
            [
                (
                    "second-write-outside-class",
                    "BRD-4",
                    files_line_of(doc, "BRD-4"),
                    ERROR,
                    FOREIGN_TRACK_MESSAGE,
                    "`source/nord/g2/g2Lib/test/tests_sched.cmake` is marked "
                    "@SCH-0 by BRD-4 of track brd; the row's class names "
                    "tracks: sched",
                )
            ],
        )


class TrackTokenResolvesThroughSection71Test(unittest.TestCase):
    """`"board".startswith("brd")` is False, and the document holds the map.

    Section 7.1 row 5 reads `nmg2-board` beside `BRD`. A raw-string prefix
    comparison happens to work for `sched`/`SCH` and fails on the one
    abbreviation that is not a prefix, so the comparison resolves the token
    to the ROW's prefix instead.
    """

    def test_a_track_word_that_is_not_a_prefix_of_the_identifier_admits_it(self):
        doc = plan(
            owner_table(
                [
                    "| `g2Lib/sim.cpp` | **BRD-11** | The CLASS of second "
                    "writers: every board-track task that extends the "
                    "simulation. |\n"
                ]
            ),
            task_block("BRD-11", "`g2Lib/sim.cpp`"),
            task_block("BRD-33", "`g2Lib/sim.cpp@BRD-11`", depends="BRD-11"),
        )
        result = secondwrite.run(doc)
        self.assertEqual(
            rows(result),
            [
                (
                    "second-write-class-undecided",
                    "BRD-33",
                    files_line_of(doc, "BRD-33"),
                    WARNING,
                    UNDECIDED_MESSAGE,
                    "`source/nord/g2/g2Lib/sim.cpp` is marked @BRD-11 by "
                    "BRD-33; the row's class reads: BRD-11 The CLASS of second "
                    "writers: every board-track task that extends the "
                    "simulation.",
                )
            ],
        )

    def test_a_token_naming_no_section_7_1_row_is_not_a_track_token(self):
        """`per-track` comes out of the phrase "the ten per-track lists".
        It names no section 7.1 row, so it is not a track token, and a class
        left with no track token at all excludes nobody."""
        doc = plan(
            owner_table(
                [
                    "| `tests/tests_cpu.cmake` | **CPU-26** | The CLASS: every "
                    "task that registers its own name — the mcf5307 analogue "
                    "of BRD-0's ten per-track lists. |\n"
                ]
            ),
            task_block("CPU-26", "`tests/tests_cpu.cmake`"),
            task_block(
                "USB-1", "`tests/tests_cpu.cmake@CPU-26`", depends="CPU-26"
            ),
        )
        result = secondwrite.run(doc)
        self.assertEqual(
            [(r[0], r[3]) for r in rows(result)],
            [("second-write-class-undecided", WARNING)],
        )

    def test_a_resolved_foreign_track_is_still_excluded(self):
        """The repair must not clear an exclusion the document really states.
        `cpu` resolves to `CPU`; a `USB-` writer carries `USB`."""
        doc = plan(
            owner_table(
                [
                    "| `tests/tests_cpu.cmake` | **CPU-26** | The CLASS: every "
                    "cpu-track task that adds its own add_test line — the "
                    "mcf5307 analogue of BRD-0's ten per-track lists. |\n"
                ]
            ),
            task_block("CPU-26", "`tests/tests_cpu.cmake`"),
            task_block(
                "USB-1", "`tests/tests_cpu.cmake@CPU-26`", depends="CPU-26"
            ),
        )
        result = secondwrite.run(doc)
        self.assertEqual(
            [(r[0], r[3], r[5]) for r in rows(result)],
            [
                (
                    "second-write-outside-class",
                    ERROR,
                    "`tests/tests_cpu.cmake` is marked @CPU-26 by USB-1 of "
                    "track usb; the row's class names tracks: cpu",
                )
            ],
        )

    def test_resolution_maps_each_readable_token_to_its_row_prefixes(self):
        doc = plan(owner_table([]))
        self.assertEqual(
            secondwrite.resolved_class_tracks(
                doc,
                "every board-track task that extends the simulation; every "
                "usbhost-track task that registers its own test",
            ),
            {"board": ("BRD",), "usbhost": ("USB",)},
        )

    def test_resolution_reads_the_prefix_column_as_well_as_the_name_column(self):
        """The plan writes both spellings — `sched-track` and `sch-track` —
        and both name section 7.1 row 6. Reading only one column would drop
        the other spelling silently, which is an exclusion deleted rather
        than repaired."""
        doc = plan(owner_table([]))
        self.assertEqual(
            secondwrite.resolved_class_tracks(doc, "every sch-track task"),
            {"sch": ("SCH",)},
        )

    def test_resolution_drops_a_token_that_names_no_track_row(self):
        doc = plan(owner_table([]))
        self.assertEqual(
            secondwrite.resolved_class_tracks(
                doc, "the ten per-track lists, and every sched-track task"
            ),
            {"sched": ("SCH",)},
        )


class BareClaimantControlTest(unittest.TestCase):
    """Case (d): a bare claimant beside the marker is test 5's territory.

    This lint implements tests 1 and 4 only. A bare claimant satisfies test 5
    and produces no finding HERE; the undecided identity for the marked entry
    is the documented exception, and it is the ONLY finding the compliant
    shape produces.
    """

    def test_the_compliant_shape_produces_only_the_undecided_identity(self):
        doc = plan(
            owner_table(
                [
                    "| `g2Lib/dsp_job.cpp` | **SCH-11** | The class of second "
                    "writer: every sch-track task that adds a condition to the "
                    "job body. |\n"
                ]
            ),
            task_block("SCH-11", "`g2Lib/dsp_job.cpp`, `test/t0_owner.cpp`"),
            task_block(
                "SCH-34", "`g2Lib/dsp_job.cpp@SCH-11`", depends="SCH-11"
            ),
        )
        result = secondwrite.run(doc)
        self.assertEqual(
            [(r[0], r[1]) for r in rows(result)],
            [("second-write-class-undecided", "SCH-34")],
        )


class MultipleEntryTest(unittest.TestCase):
    def test_each_marked_entry_is_adjudicated_on_its_own(self):
        """One `Files:` line, two marked entries, two independent verdicts.

        A path failing test 1 has no row for tests 2 and 4 to read, so that
        entry takes the missing-row finding alone; the rowed entry is judged
        against its own row and lands in test 4's undecided branch. Neither
        entry's verdict reaches the other."""
        doc = plan(
            owner_table(
                [
                    "| `g2Lib/rowed.cpp` | **AAA-1** | The class: every "
                    "aaa-track task that amends the row. |\n"
                ]
            ),
            task_block("AAA-1", "`g2Lib/rowed.cpp`"),
            task_block(
                "AAA-2",
                "`g2Lib/rowless.cpp@AAA-1`, `g2Lib/rowed.cpp@AAA-1`",
                depends="AAA-1",
            ),
        )
        result = secondwrite.run(doc)
        self.assertEqual(
            [(r[0], r[1], r[3]) for r in rows(result)],
            [
                ("second-write-no-owner-row", "AAA-2", ERROR),
                ("manifest-without-creator", "AAA-2", ERROR),
                ("second-write-class-undecided", "AAA-2", WARNING),
            ],
        )


class CoverageNoticeTest(unittest.TestCase):
    """What the report says about the tests it does NOT decide.

    A lint that implements two of five tests and prints `secondwrite: clean`
    is indistinguishable from one that ran all five and found nothing. That is
    the same reasoning `cli` applies to a lint the default run leaves out — "a
    report silent about a lint reads exactly like one in which that lint
    passed" — carried one level down, to a test WITHIN a lint.

    The notice is DERIVED from the dispatch table the run itself iterates, so
    a predicate that is not wired in cannot be claimed by the notice.
    """

    def test_the_notice_names_the_tests_the_dispatch_table_decides(self):
        doc = plan(owner_table([]), task_block("AAA-1", "`g2Lib/mine.cpp`"))
        result = secondwrite.run(doc)
        self.assertEqual(
            result.notice,
            "COVERAGE: section 7.4.2 condition 10 states 5 tests; this lint "
            "decides tests 1, 2, 3, 4, 5. A branch that turns on the prose of "
            "a class or an owner cell is reported UNDECIDED and never passed.",
        )

    def test_the_notice_is_printed_by_the_report_on_a_clean_run(self):
        doc = plan(owner_table([]), task_block("AAA-1", "`g2Lib/mine.cpp`"))
        result = secondwrite.run(doc)
        self.assertEqual(
            result.report(),
            "secondwrite: clean (1 task bodies examined)\n"
            f"  {result.notice}\n",
        )

    def test_an_undecided_test_is_ANNOUNCED_and_not_left_silent(self):
        """The KNOWN POSITIVE for the announcement itself. Hand the builder a
        table missing tests 2, 3 and 5 — the state this module shipped in —
        and the notice must SAY SO, in the words a reader needs to stop
        treating a clean run as a complete one."""
        self.assertEqual(
            secondwrite.coverage_notice((1, 4)),
            "COVERAGE: section 7.4.2 condition 10 states 5 tests; this lint "
            "decides tests 1, 4. Tests 2, 3, 5 are NOT implemented and this "
            "report says nothing about them, so a clean run here is NOT a "
            "clean condition 10. A branch that turns on the prose of a class "
            "or an owner cell is reported UNDECIDED and never passed.",
        )

    def test_a_single_missing_test_is_announced_in_the_singular(self):
        """A notice a reader trips over is a notice a reader skims. This is
        the one-missing case, which the plural wording gets wrong."""
        self.assertEqual(
            secondwrite.coverage_notice((1, 2, 3, 4)),
            "COVERAGE: section 7.4.2 condition 10 states 5 tests; this lint "
            "decides tests 1, 2, 3, 4. Test 5 is NOT implemented and this "
            "report says nothing about them, so a clean run here is NOT a "
            "clean condition 10. A branch that turns on the prose of a class "
            "or an owner cell is reported UNDECIDED and never passed.",
        )

    def test_the_notice_survives_the_no_input_guard(self):
        """A document with no task bodies fails loudly, and it still has to
        say what it would have decided."""
        doc = document.PlanDocument.from_text(TRACK_TABLE, name="inline")
        result = secondwrite.run(doc)
        self.assertEqual([f.rule for f in result.findings], ["no-input"])
        self.assertEqual(result.notice, secondwrite.coverage_notice())


class ClassDetectorUnitTest(unittest.TestCase):
    """The predicate the branch decisions rest on, held directly."""

    def test_a_class_sentence_is_every_followed_by_task_in_one_sentence(self):
        self.assertTrue(
            secondwrite.states_class(
                "The class of second writer: every sch-track task that adds a "
                "condition."
            )
        )

    def test_everybody_is_not_every(self):
        self.assertFalse(secondwrite.states_class("Everybody else asks AAA-1."))

    def test_the_word_task_alone_is_not_a_class(self):
        self.assertFalse(secondwrite.states_class("Ask the task above."))

    def test_track_limbs_are_read_from_the_hyphenated_form(self):
        self.assertEqual(
            secondwrite.class_tracks(
                "every sch-track task that adds a condition; every dsp-track "
                "task that gates step 2"
            ),
            {"sch", "dsp"},
        )

    def test_a_class_without_hyphenated_tracks_names_none(self):
        self.assertEqual(
            secondwrite.class_tracks("every task that grows the contract"),
            set(),
        )


class OwnerCellBindsPerPathTest(unittest.TestCase):
    """A multi-path row's owner cell may bind an owner PER PATH.

    Section 7.4.2 carries one row covering four cpu paths whose owner cell
    reads "CPU-10 for `machine.nim` and `cpu.nim`; CPU-6 for
    `decode_types.nim`; CPU-9 for `tests/t_logic.nim`". A reader that took the
    FIRST identifier in the cell told CPU-10 its own marker was wrong through
    a row that names CPU-10. The two grammars are told apart by `for <path>`
    and by nothing else, and first-identifier-wins stands wherever no binding
    is stated.
    """

    ROW = (
        "| `src/a.nim`, `src/b.nim`, `tests/t_logic.nim` | **AAA-1** for "
        "`a.nim` and `src/a.nim`; **AAA-2** for `b.nim`; **AAA-3** for "
        "`tests/t_logic.nim` | The class: every task. |\n"
    )

    def _doc(self, *blocks):
        return plan(
            owner_table([self.ROW]),
            task_block("AAA-1", "`src/a.nim`"),
            task_block("AAA-2", "`src/b.nim`"),
            task_block("AAA-3", "`tests/t_logic.nim`"),
            *blocks,
        )

    def test_each_path_of_a_multi_path_row_resolves_to_its_bound_owner(self):
        doc = self._doc()
        self.assertEqual(doc.owner_of("src/a.nim").ident, "AAA-1")
        self.assertEqual(doc.owner_of("src/b.nim").ident, "AAA-2")
        self.assertEqual(doc.owner_of("tests/t_logic.nim").ident, "AAA-3")

    def test_a_marker_carrying_the_bound_owner_raises_no_test_2_finding(self):
        doc = self._doc(
            task_block("AAA-9", "`src/b.nim@AAA-2`", depends="AAA-2")
        )
        result = secondwrite.run(doc)
        self.assertEqual(
            [r for r in rows(result) if r[0] == "second-write-wrong-owner"],
            [],
        )

    def test_a_marker_carrying_another_paths_owner_is_still_reported(self):
        """The KNOWN POSITIVE. AAA-1 owns `src/a.nim` and nothing else in the
        row, so a marker writing `src/b.nim@AAA-1` names the wrong owner and
        the finding must name the BOUND owner of the path it writes."""
        doc = self._doc(
            task_block("AAA-9", "`src/b.nim@AAA-1`", depends="AAA-1")
        )
        result = secondwrite.run(doc)
        self.assertEqual(
            [r for r in rows(result) if r[0] == "second-write-wrong-owner"],
            [
                (
                    "second-write-wrong-owner",
                    "AAA-9",
                    files_line_of(doc, "AAA-9"),
                    ERROR,
                    WRONG_OWNER_MESSAGE,
                    "`src/b.nim` is marked @AAA-1 by AAA-9; section 7.4.2's "
                    "row names AAA-2 as its owner",
                )
            ],
        )

    def test_a_cell_stating_no_binding_still_takes_the_first_identifier(self):
        """The grammar the fallback exists for: `**DSP-0**, with **DSP-1** as
        the one declared second writer`. The first name is the owner there and
        every later one is a declared second writer."""
        doc = plan(
            owner_table(
                [
                    "| `src/c.nim` | **AAA-1**, with **AAA-2** as the one "
                    "declared second writer | The class: every task. |\n"
                ]
            ),
            task_block("AAA-1", "`src/c.nim`"),
            task_block("AAA-2", "`src/other.nim`"),
        )
        self.assertEqual(doc.owner_of("src/c.nim").ident, "AAA-1")

    def test_a_binding_matches_a_whole_path_segment_and_never_a_substring(self):
        """`logic.nim` is a substring of `tests/t_logic.nim` and names a
        different file. A binding that matched on the raw tail would hand
        `tests/t_logic.nim` to the owner of `logic.nim`, and section 7.4.2
        names that exact trap for a basename grep."""
        doc = plan(
            owner_table(
                [
                    "| `src/logic.nim`, `tests/t_logic.nim` | **AAA-2** for "
                    "`logic.nim` | The class: every task. |\n"
                ]
            ),
            task_block("AAA-1", "`tests/t_logic.nim`"),
            task_block("AAA-2", "`src/logic.nim`"),
        )
        self.assertEqual(doc.owner_of("src/logic.nim").ident, "AAA-2")
        self.assertEqual(
            document.bound_owner("AAA-2 for logic.nim", "tests/t_logic.nim"),
            None,
        )

    def test_a_binding_naming_no_task_block_leaves_the_owner_unresolved(self):
        """A bound identifier that is no task block states no owner this tool
        can resolve, and falling back to the first identifier would answer
        with the owner of a DIFFERENT path in the same row."""
        doc = plan(
            owner_table(
                [
                    "| `src/a.nim`, `src/b.nim` | **AAA-1** for `a.nim`; "
                    "**ZZZ-9** for `b.nim` | The class: every task. |\n"
                ]
            ),
            task_block("AAA-1", "`src/a.nim`"),
        )
        self.assertIsNone(doc.owner_of("src/b.nim"))


class RepositoryKeyedOwnerRowTest(unittest.TestCase):
    """The owner table is keyed on the (repository, path) PAIR.

    Section 7.4.2's own preamble states it — "the same repository-relative
    path names different files in different repositories ... the criterion is
    keyed on the pair (repository, path)" — and this module's docstring
    repeats it. The parser dropped the Repository column, so two rows for
    `CMakeLists.txt` collapsed into one dict key and the second overwrote the
    first: every query answered with the fork's owner, and the `mcf5307`
    task's correct marker was reported wrong.
    """

    ROWS = [
        "| `CMakeLists.txt` | **CPU-26** | `mcf5307` | The class: every "
        "cpu-track task that registers its own name. |\n",
        "| `CMakeLists.txt` | **BRD-0** | `gearmulator` fork | The class: "
        "every board-track task that registers its own name. |\n",
    ]

    def _doc(self, *blocks):
        return plan(
            repository_owner_table(self.ROWS),
            task_block("CPU-26", "`CMakeLists.txt`"),
            task_block("BRD-0", "`CMakeLists.txt`"),
            *blocks,
        )

    def test_each_repositorys_row_answers_its_own_repositorys_query(self):
        doc = self._doc()
        self.assertEqual(
            doc.owner_cell("CMakeLists.txt", ("mcf5307",)), "CPU-26"
        )
        self.assertEqual(
            doc.owner_cell("CMakeLists.txt", ("gearmulator fork",)), "BRD-0"
        )

    def test_the_mechanism_comes_from_the_same_row_as_the_owner(self):
        """A class read from one repository's row and an owner from another's
        would adjudicate a marker against prose written for a different
        file."""
        doc = self._doc()
        self.assertEqual(
            doc.mechanism_cell("CMakeLists.txt", ("mcf5307",)),
            "The class: every cpu-track task that registers its own name.",
        )
        self.assertEqual(
            doc.mechanism_cell("CMakeLists.txt", ("gearmulator fork",)),
            "The class: every board-track task that registers its own name.",
        )

    def test_a_marker_is_held_against_the_row_of_its_writers_repository(self):
        """CPU-1 writes in `mcf5307`, where CPU-26 owns the list. The fork's
        row names BRD-0 and is a different file that never merges with it."""
        doc = self._doc(
            task_block("CPU-1", "`CMakeLists.txt@CPU-26`", depends="CPU-26"),
            task_block("BRD-1", "`CMakeLists.txt@BRD-0`", depends="BRD-0"),
        )
        result = secondwrite.run(doc)
        self.assertEqual(
            [r for r in rows(result) if r[0] == "second-write-wrong-owner"],
            [],
        )

    def test_a_marker_naming_the_other_repositorys_owner_is_reported(self):
        """The KNOWN POSITIVE. A `mcf5307` task marking the fork's owner has
        named a task that owns a different file."""
        doc = self._doc(
            task_block("CPU-1", "`CMakeLists.txt@BRD-0`", depends="BRD-0"),
        )
        result = secondwrite.run(doc)
        self.assertEqual(
            [r for r in rows(result) if r[0] == "second-write-wrong-owner"],
            [
                (
                    "second-write-wrong-owner",
                    "CPU-1",
                    files_line_of(doc, "CPU-1"),
                    ERROR,
                    WRONG_OWNER_MESSAGE,
                    "`CMakeLists.txt` is marked @BRD-0 by CPU-1; section "
                    "7.4.2's row names CPU-26 as its owner",
                )
            ],
        )

    def test_a_writer_whose_repository_no_row_names_still_finds_the_row(self):
        """A repository the row does not name leaves the pair unmatched, and
        the path alone still answers. Refusing to answer would turn every row
        whose Repository cell is prose — `all seven repositories`, `the
        workspace, outside every repository` — into a missing row, which is
        test 1's ERROR reported for a row the document holds."""
        doc = plan(
            repository_owner_table(
                [
                    "| `docs/x.md` | **SCH-0** | the workspace, outside every "
                    "repository | The class: every task. |\n"
                ]
            ),
            task_block("SCH-0", "`docs/x.md`"),
            task_block("SCH-30", "`docs/x.md@SCH-0`", depends="SCH-0"),
        )
        result = secondwrite.run(doc)
        self.assertEqual(
            [r[0] for r in rows(result)], ["second-write-class-undecided"]
        )

    def test_a_table_without_a_repository_column_keys_on_the_path_alone(self):
        doc = plan(
            owner_table(["| `src/a.nim` | **AAA-1** | The class: every task. |\n"]),
            task_block("AAA-1", "`src/a.nim`"),
        )
        self.assertEqual(doc.owner_cell("src/a.nim", ("mcf5307",)), "AAA-1")


class RepositoryNameTest(unittest.TestCase):
    """The one normalizer both tables are read through.

    Section 7.1's Repository column and section 7.4.2's spell the same
    repository two ways — `` `gearmulator` fork `` and `gearmulator` — and a
    raw-string comparison of the two cells matches nothing at all.
    """

    def test_a_fork_is_named_by_its_repository(self):
        self.assertEqual(
            document.repository_names("`gearmulator` fork"), {"gearmulator"}
        )

    def test_a_plain_name_is_itself(self):
        self.assertEqual(document.repository_names("`mcf5307`"), {"mcf5307"})

    def test_a_cell_naming_several_repositories_names_each_of_them(self):
        self.assertEqual(
            document.repository_names("`mcf5307`, `gearmulator` fork"),
            {"mcf5307", "gearmulator"},
        )

    def test_an_and_joins_names_as_a_comma_does(self):
        self.assertEqual(
            document.repository_names(
                "the `gearmulator` fork and the `dsp56300` fork"
            ),
            {"gearmulator", "dsp56300"},
        )

    def test_an_em_dash_annotation_is_not_part_of_the_name(self):
        self.assertEqual(
            document.repository_names("`dsp56300` fork — one file in each"),
            {"dsp56300"},
        )


class MechanismCellTest(unittest.TestCase):
    """The parser keeps the mechanism column the class prose lives in.

    The direct queries use CANONICAL spellings, because that is the contract
    `owner_cell` already states and this accessor mirrors it.
    """

    def test_the_mechanism_cell_is_kept_beside_the_owner_cell(self):
        doc = plan(
            owner_table(["| `g2Lib/a.cpp` | **AAA-1** | The class: every task. |\n"]),
            task_block("AAA-2", "`g2Lib/a.cpp@AAA-1`"),
        )
        canonical = document.canonical_path("g2Lib/a.cpp")
        self.assertEqual(
            doc.mechanism_cell(canonical),
            "The class: every task.",
        )
        self.assertEqual(doc.owner_cell(canonical), "AAA-1")

    def test_a_directory_row_carries_its_mechanism_over_the_paths_below(self):
        doc = plan(
            owner_table(["| `g2Lib/` | **AAA-1** | The class: every task. |\n"]),
            task_block("AAA-2", "`g2Lib/deep/b.cpp@AAA-1`"),
        )
        self.assertEqual(
            doc.mechanism_cell(document.canonical_path("g2Lib/deep/b.cpp")),
            "The class: every task.",
        )

    def test_a_file_row_wins_over_a_directory_row_for_both_cells(self):
        doc = plan(
            owner_table(
                [
                    "| `g2Lib/` | **AAA-1** | Directory mechanism. |\n",
                    "| `g2Lib/a.cpp` | **AAA-2** | File mechanism. |\n",
                ]
            ),
            task_block("AAA-3", "`g2Lib/a.cpp@AAA-2`"),
        )
        canonical = document.canonical_path("g2Lib/a.cpp")
        self.assertEqual(doc.mechanism_cell(canonical), "File mechanism.")
        self.assertEqual(doc.owner_cell(canonical), "AAA-2")

    def test_a_two_column_row_yields_none_not_a_crash(self):
        """None records that this table carries no mechanism column; an empty
        string records a column present and a cell empty. The two are
        different documents and the accessor keeps them apart."""
        doc = plan(
            bare_owner_table(["| `g2Lib/a.cpp` | **AAA-1** |\n"]),
            task_block("AAA-2", "`g2Lib/a.cpp@AAA-1`"),
        )
        self.assertIsNone(doc.mechanism_cell(document.canonical_path("g2Lib/a.cpp")))


def wave_table(rows):
    """Section 7.2's wave table, carrying the given `| label | order | tasks |`
    rows. An order row is decided against THIS table and against nothing else,
    so a fixture that omits it states no order at all."""
    body = "".join(rows)
    return (
        "### 7.2 The waves\n"
        "\n"
        "| Wave | Order | The tasks in it |\n"
        "|---|---|---|\n"
        f"{body}"
    )


ORDER_ROW = (
    "| `g2TestConsole/` | **serial by wave** | SCH-11 creates `main.cpp` in "
    "Wave 4a and BRD-29 extends it in Wave 4b. No two writers of one file "
    "share a wave. This is the one shared path the plan resolves by order "
    "rather than by ownership, and it says so. |\n"
)

MAIN_CPP = document.canonical_path("g2TestConsole/main.cpp")


class SecondWriteOrderRowTest(unittest.TestCase):
    """The THIRD shape: a row satisfied by ORDER, not by ownership.

    Section 7.4.2's `g2TestConsole/` row states `serial by wave` in its owner
    cell and calls itself "the one shared path the plan resolves by ORDER
    rather than by OWNERSHIP". It is neither a readable ownership class nor
    undecidable prose: it names a mechanism this lint can check against
    section 7.2's wave table, in two halves.

      * TEST 2, who the owner is. An order row's owner is the writer section
        7.2 places EARLIEST. A marker carrying that identifier names the
        row's owner; one carrying another writer's does not.
      * TEST 4, who is admitted. Every writer whose wave order no OTHER
        writer of the same path holds. "No two writers of one file share a
        wave" is the row's own mechanism, and it is a property of the PATH's
        writer set and not of the directory's.

    A writer section 7.2 places in no row leaves both halves unresolved, and
    that is ANNOUNCED under the same two rule ids rather than passed.
    """

    def test_an_order_row_whose_writers_hold_distinct_waves_is_satisfied(self):
        """The DISPOSING case. SCH-11 creates the file in wave 4a and BRD-29
        extends it in 4b. Nothing is undecided and nothing is refused: the
        marker names the earliest writer, and the two writers hold different
        wave positions."""
        doc = plan(
            wave_table(["| 4a | 7 | SCH-11 |\n", "| 4b | 8 | BRD-29 |\n"]),
            owner_table([ORDER_ROW]),
            task_block("SCH-11", "`g2TestConsole/main.cpp`"),
            task_block(
                "BRD-29", "`g2TestConsole/main.cpp@SCH-11`", depends="SCH-11"
            ),
        )
        self.assertEqual(rows(secondwrite.run(doc)), [])

    def test_two_writers_of_one_path_sharing_a_wave_are_reported(self):
        """The KNOWN POSITIVE for the order predicate. BRD-29 and CPU-9 both
        write `main.cpp` and section 7.2 places both in wave 4b, so the row's
        own mechanism — no two writers of one file share a wave — is false of
        the document that states it. Each colliding writer hears about it and
        names the other; a writer that shares a wave with nobody does not."""
        doc = plan(
            wave_table(
                [
                    "| 4a | 7 | SCH-11 |\n",
                    "| 4b | 8 | BRD-29, CPU-9 |\n",
                ]
            ),
            owner_table([ORDER_ROW]),
            task_block("SCH-11", "`g2TestConsole/main.cpp`"),
            task_block(
                "BRD-29", "`g2TestConsole/main.cpp@SCH-11`", depends="SCH-11"
            ),
            task_block(
                "CPU-9", "`g2TestConsole/main.cpp@SCH-11`", depends="SCH-11"
            ),
        )
        result = secondwrite.run(doc)
        self.assertEqual(
            rows(result),
            [
                (
                    "second-write-outside-class",
                    "BRD-29",
                    files_line_of(doc, "BRD-29"),
                    ERROR,
                    ORDER_COLLISION_MESSAGE,
                    f"`{MAIN_CPP}` is marked @SCH-11 by BRD-29; the owner row "
                    "resolves this path by order, and section 7.2 places "
                    "BRD-29 in wave 4b together with CPU-9",
                ),
                (
                    "second-write-outside-class",
                    "CPU-9",
                    files_line_of(doc, "CPU-9"),
                    ERROR,
                    ORDER_COLLISION_MESSAGE,
                    f"`{MAIN_CPP}` is marked @SCH-11 by CPU-9; the owner row "
                    "resolves this path by order, and section 7.2 places "
                    "CPU-9 in wave 4b together with BRD-29",
                ),
            ],
        )

    def test_a_writer_the_wave_table_places_nowhere_is_announced_undecided(self):
        """The wave data comes from the PLAN. A writer section 7.2 places in
        no row leaves both halves of the order unresolved — the earliest
        writer is unknown and so is whether anybody shares a wave — and both
        are ANNOUNCED rather than silently passed."""
        doc = plan(
            wave_table(["| 4a | 7 | SCH-11 |\n", "| 4b | 8 | BRD-29 |\n"]),
            owner_table([ORDER_ROW]),
            task_block("SCH-11", "`g2TestConsole/main.cpp`"),
            task_block(
                "BRD-29", "`g2TestConsole/main.cpp@SCH-11`", depends="SCH-11"
            ),
            task_block(
                "CPU-9", "`g2TestConsole/main.cpp@SCH-11`", depends="SCH-11"
            ),
        )
        result = secondwrite.run(doc)
        self.assertEqual(
            rows(result),
            [
                (
                    "second-write-owner-undecided",
                    "BRD-29",
                    files_line_of(doc, "BRD-29"),
                    WARNING,
                    ORDER_OWNER_UNDECIDED_MESSAGE,
                    f"`{MAIN_CPP}` is marked @SCH-11 by BRD-29; the owner "
                    "cell reads: serial by wave, and section 7.2's wave table "
                    "places CPU-9 in no row",
                ),
                (
                    "second-write-class-undecided",
                    "BRD-29",
                    files_line_of(doc, "BRD-29"),
                    WARNING,
                    ORDER_ADMISSION_UNDECIDED_MESSAGE,
                    f"`{MAIN_CPP}` is marked @SCH-11 by BRD-29; the owner row "
                    "resolves this path by order, and section 7.2's wave "
                    "table places CPU-9 in no row",
                ),
                (
                    "second-write-owner-undecided",
                    "CPU-9",
                    files_line_of(doc, "CPU-9"),
                    WARNING,
                    ORDER_OWNER_UNDECIDED_MESSAGE,
                    f"`{MAIN_CPP}` is marked @SCH-11 by CPU-9; the owner "
                    "cell reads: serial by wave, and section 7.2's wave table "
                    "places CPU-9 in no row",
                ),
                (
                    "second-write-class-undecided",
                    "CPU-9",
                    files_line_of(doc, "CPU-9"),
                    WARNING,
                    ORDER_ADMISSION_UNDECIDED_MESSAGE,
                    f"`{MAIN_CPP}` is marked @SCH-11 by CPU-9; the owner row "
                    "resolves this path by order, and section 7.2's wave "
                    "table places CPU-9 in no row",
                ),
            ],
        )

    def test_a_marker_naming_other_than_the_earliest_writer_is_reported(self):
        """The order half of test 2. SCH-11 writes in wave 4a and SCH-12 in
        4b, so the row's owner is SCH-11; BRD-29 marks the path @SCH-12 and
        names a writer that is not the earliest. Test 4 is silent: BRD-29's
        own wave 5a is held by no other writer."""
        doc = plan(
            wave_table(
                [
                    "| 4a | 7 | SCH-11 |\n",
                    "| 4b | 8 | SCH-12 |\n",
                    "| 5a | 9 | BRD-29 |\n",
                ]
            ),
            owner_table([ORDER_ROW]),
            task_block("SCH-11", "`g2TestConsole/main.cpp`"),
            task_block("SCH-12", "`g2TestConsole/main.cpp`"),
            task_block(
                "BRD-29", "`g2TestConsole/main.cpp@SCH-12`", depends="SCH-12"
            ),
        )
        result = secondwrite.run(doc)
        self.assertEqual(
            rows(result),
            [
                (
                    "second-write-wrong-owner",
                    "BRD-29",
                    files_line_of(doc, "BRD-29"),
                    ERROR,
                    ORDER_WRONG_OWNER_MESSAGE,
                    f"`{MAIN_CPP}` is marked @SCH-12 by BRD-29; the owner "
                    "cell reads: serial by wave, and the writer section 7.2 "
                    "places earliest is SCH-11, in wave 4a",
                ),
            ],
        )


if __name__ == "__main__":
    unittest.main()
