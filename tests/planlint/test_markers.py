"""Tests for the marker lint — the union half of section 24.6's citation form.

A `DONE` marker records ONE measured fact: the commits its citation NAMES
touched every path the task's `Files:` line declares that this machine could
resolve, and the citation names which commit covered which path.

The second half of that sentence was satisfiable by a citation that named
almost none of the work it rested on. A marker stating a commit COUNT while
quoting only the NEWEST sha passed it, and markers stood in that state until
a hand-built scan found them. This lint is the rule that reads them.

It decides the NAMING question and no other: a declared path that no entry
names. Whether a named sha really touched the path it claims is the `citations`
lint's question, and that one needs a repository.
"""

import unittest

from tests.planlint.support import load_fixture

from planlint import markers
from planlint.document import PlanDocument


def rows(result):
    return [
        (f.rule, f.task, f.line, f.severity, f.evidence) for f in result.findings
    ]


def one_task(files, marker):
    return PlanDocument.from_text(
        "## 9. The tasks\n"
        "\n"
        "**AAA-1 · A task** — T0\n"
        f"Files: {files}\n"
        "Depends: none\n"
        "Check: `ctest --test-dir build --no-tests=error -R t0_one`\n"
        f"{marker}\n",
        name="inline",
    )


class PathUncitedTest(unittest.TestCase):
    def test_a_declared_path_no_entry_names_is_reported(self):
        result = markers.run(load_fixture("neg_marker_path_uncited.md"))

        self.assertEqual(
            [row for row in rows(result) if row[0] == "done-marker-path-uncited"],
            [
                (
                    "done-marker-path-uncited",
                    "AAA-2",
                    23,
                    "ERROR",
                    "`src/beta.h` is declared by the `Files:` line of AAA-2 and "
                    "named by none of the 1 cited entry: `axiomantic/core` "
                    "`3333333`",
                )
            ],
        )

    def test_the_message_states_the_claim_the_citation_makes(self):
        result = markers.run(load_fixture("neg_marker_path_uncited.md"))

        self.assertEqual(
            [
                f.message
                for f in result.findings
                if f.rule == "done-marker-path-uncited"
            ],
            [
                "a completion marker's citation names no commit for a path the "
                "task's `Files:` line declares. The marker's whole claim is "
                "that the commits it names touched every declared path, so a "
                "path no entry names leaves a reader unable to tell a citation "
                "that is SHORT from one that is FALSE"
            ],
        )

    def test_a_marker_whose_entries_name_every_declared_path_is_silent(self):
        doc = one_task(
            "`src/one.cpp`, `src/two.cpp`",
            "**DONE. CITED PER DECLARED PATH:** `axiomantic/core` `1111111` → "
            "`src/one.cpp`, `src/two.cpp`.",
        )

        self.assertEqual(markers.run(doc).findings, [])

    def test_a_build_target_is_not_a_path_and_is_not_compared(self):
        """The `Files:` line names build targets after the word `targets`. No
        path resolves one, so no entry can name it."""
        doc = one_task(
            "`src/one.cpp`, targets `core_tests`",
            "**DONE. CITED PER DECLARED PATH:** `axiomantic/core` `1111111` → "
            "`src/one.cpp`.",
        )

        self.assertEqual(markers.run(doc).findings, [])

    def test_a_glob_is_undecidable_and_is_not_compared(self):
        """WHAT THIS RULE CANNOT DECIDE, asserted rather than assumed. A glob
        names a SET of files and no entry names it literally, so a literal set
        comparison has no operand. Reporting it would fire on every corpus
        declaration in the plan."""
        doc = one_task(
            "`src/one.cpp`, `corpus/move_*.json`",
            "**DONE. CITED PER DECLARED PATH:** `axiomantic/core` `1111111` → "
            "`src/one.cpp`.",
        )

        self.assertEqual(markers.run(doc).findings, [])

    def test_an_entry_that_names_no_directory_and_no_suffix_is_not_compared(self):
        """REPO-14 declares `nmg2-tools` and DSP-0 declares `dsp56300`. Both
        name a REPOSITORY and not a file, and a commit cannot touch one."""
        doc = one_task(
            "`src/one.cpp`, `nmg2-tools`",
            "**DONE. CITED PER DECLARED PATH:** `axiomantic/core` `1111111` → "
            "`src/one.cpp`.",
        )

        self.assertEqual(markers.run(doc).findings, [])

    def test_a_second_writer_marker_is_stripped_before_the_compare(self):
        """Section 1.1.1 rule D: `<path>@<OWNER-ID>` declares a write to a file
        another task owns. The write still happened, so the path is compared —
        with the marker off, or the two sides compare two spellings."""
        doc = one_task(
            "`src/one.cpp`, `tests/tests_cpu.cmake@CPU-26`",
            "**DONE. CITED PER DECLARED PATH:** `axiomantic/core` `1111111` → "
            "`src/one.cpp`, `tests/tests_cpu.cmake`.",
        )

        self.assertEqual(markers.run(doc).findings, [])

    def test_an_abbreviated_declaration_and_a_canonical_citation_name_one_file(self):
        """Section 1.1.1 rule B, applied to both operands out of one expander."""
        doc = one_task(
            "`g2Lib/test/gatedFixture.h`",
            "**DONE. CITED PER DECLARED PATH:** `axiomantic/core` `1111111` → "
            "`source/nord/g2/g2Lib/test/gatedFixture.h`.",
        )

        self.assertEqual(markers.run(doc).findings, [])

    def test_a_task_with_no_marker_is_not_reported(self):
        result = markers.run(load_fixture("neg_marker_path_uncited.md"))

        self.assertEqual([row[1] for row in rows(result)], ["AAA-2", "AAA-3"])


class CitationNotInFormTest(unittest.TestCase):
    """The UNDECIDED branch, reported and never passed.

    Most of the plan's markers predate the citation form. Their coverage is
    not decidable from the text, because they assign no path to any commit. A
    rule that fell silent on them would report clean over the very markers that
    carry the risk, and a form whose observance and whose violation produce
    identical output is the shape this project refuses.
    """

    def test_a_marker_with_no_entry_is_reported_undecided(self):
        result = markers.run(load_fixture("neg_marker_path_uncited.md"))

        self.assertEqual(
            [
                row
                for row in rows(result)
                if row[0] == "done-marker-citation-not-in-form"
            ],
            [
                (
                    "done-marker-citation-not-in-form",
                    "AAA-3",
                    30,
                    "WARNING",
                    "the marker carries no `→` entry, so the coverage of 1 "
                    "declared path is undecided: `tests/t0_gamma.cpp`",
                )
            ],
        )

    def test_the_message_names_the_form_the_marker_does_not_carry(self):
        result = markers.run(load_fixture("neg_marker_path_uncited.md"))

        self.assertEqual(
            [
                f.message
                for f in result.findings
                if f.rule == "done-marker-citation-not-in-form"
            ],
            [
                "a completion marker states no per-path citation, so which "
                "commit covers which declared path is UNDECIDED. This is "
                "reported rather than passed, because a silence here reads "
                "exactly like coverage. Section 24.6's form is "
                "`<owner>/<repo>`, then the commit sha, then `→`, then the "
                "declared paths that commit touched, with entries separated "
                "by `;`"
            ],
        )

    def test_a_marker_on_a_task_that_declares_no_comparable_path_is_silent(self):
        """No declared path means nothing goes undecided. A finding here would
        be a rule firing where it has no subject."""
        doc = one_task("targets `core_tests`", "**DONE on 2026-01-01, commit `1111111`.**")

        self.assertEqual(markers.run(doc).findings, [])


class NoInputTest(unittest.TestCase):
    def test_a_document_with_no_task_block_is_a_hard_error(self):
        result = markers.run(
            PlanDocument.from_text("# A document with no task\n", name="inline")
        )

        self.assertEqual(
            [(f.rule, f.message, f.severity) for f in result.findings],
            [("no-input", "the marker lint examined 0 task bodies", "ERROR")],
        )


if __name__ == "__main__":
    unittest.main()
