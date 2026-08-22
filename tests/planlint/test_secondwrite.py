"""Tests for the second-write lint — condition 10, tests 1 and 4 of section 7.4.2.

Section 7.4.2 states five tests every completion marker must pass. Tests 2, 3
and 5 belong to other rules. This file covers the two implemented here:

  * test 1 — `second-write-no-owner-row`: the document holds no owner row for
    the path the marker names, so the marker's own premise is refuted;
  * test 4 — `second-write-outside-class`: the writing task is outside the
    class the owner row states, or the row states no class at all and so
    admits nobody.

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


def task_block(ident, files, line_note=""):
    """One task block. `line_note` pads the body so line numbers stay put."""
    return (
        f"**{ident} · A task** — T0\n"
        f"Files: {files}\n"
        "Depends: none\n"
        "Check: `ctest --test-dir build --no-tests=error -R t0_one`. "
        f"Registered with `add_test(NAME t0_one ...)`.{line_note}\n"
    )


def plan(*sections):
    return document.PlanDocument.from_text(
        "## 9. The tasks\n" + "\n".join(sections),
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


class SecondWriteNoOwnerRowTest(unittest.TestCase):
    """Condition-10 test 1: the owner row the marker asserts must exist."""

    def test_a_marker_whose_path_has_no_owner_row_is_reported(self):
        doc = plan(task_block("SCH-10", "`g2Lib/esai_frame.h@SCH-9`"))
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
            task_block("SCH-34", "`g2Lib/dsp_job.cpp@SCH-11`"),
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
            task_block("SCH-34", "`g2Lib/dsp_job.cpp@SCH-11`"),
        )
        result = secondwrite.run(doc)
        self.assertEqual(
            [(r[0], r[3]) for r in rows(result)],
            [("second-write-class-undecided", WARNING)],
        )

    def test_the_rows_own_writer_is_not_a_second_writer(self):
        """The owner writes by ownership, not by class membership. Demanding
        that the owner sit inside its own class is a category error."""
        doc = plan(
            owner_table(["| `g2Lib/dsp_job.cpp` | **SCH-11** | Ask SCH-11. |\n"]),
            task_block("SCH-11", "`g2Lib/dsp_job.cpp@SCH-11`"),
        )
        result = secondwrite.run(doc)
        self.assertEqual(rows(result), [])

    def test_a_writer_outside_every_named_track_is_outside_the_class(self):
        doc = plan(
            owner_table(
                [
                    "| `g2Lib/dsp_job.cpp` | **SCH-11** | The class of second "
                    "writer: every sch-track task that adds a condition to the "
                    "job body. |\n"
                ]
            ),
            task_block("BRD-4", "`g2Lib/dsp_job.cpp@SCH-11`"),
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
            task_block("SCH-34", "`g2Lib/dsp_job.cpp@SCH-11`"),
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
                    "row's class reads: The class of second writer: every sch-track "
                    "task that adds a condition to the job body.",
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
            task_block("USB-3", "`source/nord/g2/g2UsbHost/list.cmake@USB-0`"),
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
            task_block("BRD-2", "`include/mcf5307.h@CPU-0`"),
        )
        result = secondwrite.run(doc)
        self.assertEqual(
            [r[0] for r in rows(result)],
            ["second-write-class-undecided"],
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
            task_block("SCH-34", "`g2Lib/dsp_job.cpp@SCH-11`"),
        )
        result = secondwrite.run(doc)
        self.assertEqual(
            [(r[0], r[1]) for r in rows(result)],
            [("second-write-class-undecided", "SCH-34")],
        )


class MultipleEntryTest(unittest.TestCase):
    def test_each_marked_entry_yields_its_own_single_finding(self):
        """A path failing test 1 has no row for test 4 to read, so one entry
        yields at most one finding. The rowed entry takes its own, from test
        4's undecided branch — never two findings for one entry."""
        doc = plan(
            owner_table(
                [
                    "| `g2Lib/rowed.cpp` | **AAA-1** | The class: every "
                    "aaa-track task that amends the row. |\n"
                ]
            ),
            task_block(
                "AAA-2",
                "`g2Lib/rowless.cpp@AAA-1`, `g2Lib/rowed.cpp@AAA-1`",
            ),
        )
        result = secondwrite.run(doc)
        self.assertEqual(
            [(r[0], r[1], r[3]) for r in rows(result)],
            [
                ("second-write-no-owner-row", "AAA-2", ERROR),
                ("second-write-class-undecided", "AAA-2", WARNING),
            ],
        )


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


if __name__ == "__main__":
    unittest.main()
