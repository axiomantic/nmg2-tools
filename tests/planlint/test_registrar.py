"""Tests for the registrar-reachability lint.

A task whose `Check:` runs `ctest -R <name>` needs the task that CREATES the test
source and the task that REGISTERS the directory inside its transitive
dependency closure. Otherwise the check cannot pass on the day the task is
declared complete, which is the mirror of a check that cannot fail.
"""

import unittest

from tests.planlint.support import load_fixture

from planlint import registrar
from planlint.document import PlanDocument
from planlint.finding import ERROR


def run(name):
    return registrar.run(load_fixture(name))


class ClosureTest(unittest.TestCase):
    def test_the_closure_holds_every_transitive_dependency(self):
        doc = load_fixture("neg_registrar_unreachable.md")

        self.assertEqual(
            registrar.closure(doc, "AAA-4"), {"AAA-1", "AAA-2", "AAA-3", "AAA-4"}
        )

    def test_a_task_with_no_dependency_is_its_own_closure(self):
        doc = load_fixture("neg_registrar_unreachable.md")

        self.assertEqual(registrar.closure(doc, "AAA-1"), {"AAA-1"})


class CreatorsOfTest(unittest.TestCase):
    """A creator lookup that returns the FIRST basename match in document order
    ignores the directory, so with two same-named test files the second is
    invisible and the verdict depends on file position. Both halves return a
    list, and every candidate must be reachable — the lint cannot tell which
    source the name resolves to, so it may excuse none of them.
    """

    TWO_CREATORS = (
        "**AAA-1 · The first carrier** — T0\n"
        "Files: `alpha/test/CMakeLists.txt`, `alpha/test/t0_shared.cpp`\n"
        "Design: 1\n"
        "Depends: none\n"
        "Check: `ctest --test-dir build --no-tests=error -R ^t0_shared$`. "
        "Registered with `add_test(NAME t0_shared ...)`.\n"
        "\n"
        "**BBB-1 · The second carrier** — T0\n"
        "Files: `beta/test/CMakeLists.txt`, `beta/test/t0_shared.cpp`\n"
        "Design: 2\n"
        "Depends: none\n"
        "Check: `ctest --test-dir build --no-tests=error -R ^t0_shared$`. "
        "Registered with `add_test(NAME t0_shared ...)`.\n"
    )

    def document(self):
        return PlanDocument.from_text(self.TWO_CREATORS, name="inline")

    def test_every_task_that_creates_the_stem_is_returned_in_document_order(self):
        doc = self.document()

        self.assertEqual(
            [(task.ident, item) for task, item in registrar.creators_of(doc, "t0_shared")],
            [("AAA-1", "alpha/test/t0_shared.cpp"), ("BBB-1", "beta/test/t0_shared.cpp")],
        )

    def test_a_name_no_files_line_creates_returns_an_empty_list(self):
        self.assertEqual(registrar.creators_of(self.document(), "t0_absent"), [])

    def test_the_second_creator_outside_the_closure_is_reported(self):
        """AAA-1 comes first in document order, so the first-match read excused
        BBB-1 entirely. Both tasks run `-R ^t0_shared$` and neither declares the
        other."""
        result = registrar.run(self.document())

        self.assertEqual(
            sorted((f.rule, f.task, f.evidence) for f in result.findings),
            [
                (
                    "creator-outside-closure",
                    "AAA-1",
                    "-R t0_shared needs BBB-1, which creates "
                    "`beta/test/t0_shared.cpp`; BBB-1 is not in AAA-1's dependency "
                    "closure",
                ),
                (
                    "creator-outside-closure",
                    "BBB-1",
                    "-R t0_shared needs AAA-1, which creates "
                    "`alpha/test/t0_shared.cpp`; AAA-1 is not in BBB-1's dependency "
                    "closure",
                ),
                (
                    "registrar-outside-closure",
                    "AAA-1",
                    "-R t0_shared needs BBB-1, which creates "
                    "`beta/test/CMakeLists.txt`; BBB-1 is not in AAA-1's dependency "
                    "closure",
                ),
                (
                    "registrar-outside-closure",
                    "BBB-1",
                    "-R t0_shared needs AAA-1, which creates "
                    "`alpha/test/CMakeLists.txt`; AAA-1 is not in BBB-1's dependency "
                    "closure",
                ),
            ],
        )

    def test_an_empty_name_is_created_by_no_files_line(self):
        """`-R ^$` strips to the empty name, and a `Files:` entry naming a
        DIRECTORY has an empty basename. The empty name matched that entry and
        the registrar lint resolved it to a task that creates no test at all."""
        doc = load_fixture("neg_check_empty_r_argument.md")

        self.assertEqual(registrar.creators_of(doc, ""), [])
        self.assertEqual(
            sorted((f.rule, f.task, f.evidence) for f in registrar.run(doc).findings),
            [
                (
                    "registrar-unknown",
                    "AAA-1",
                    "-R ; no `Files:` line creates a source or a target for that name",
                )
            ],
        )


class RegistrarLintTest(unittest.TestCase):
    def test_the_clean_plan_reports_nothing(self):
        result = run("clean_plan.md")

        self.assertEqual(result.findings, [])
        # One `-R` argument per task check that runs `ctest`. DDD-1 runs
        # `pytest` and passes no `-R`. A milestone row is not a task and has no
        # dependency closure, so the registrar lint does not read one.
        self.assertEqual(result.examined, 7)

    def test_a_registrar_outside_the_closure_is_reported_with_the_path(self):
        result = run("neg_registrar_unreachable.md")

        self.assertIn(
            (
                "registrar-outside-closure",
                "AAA-1",
                "-R t0_abi_header needs AAA-3, which creates "
                "`tests/CMakeLists.txt`; AAA-3 is not in AAA-1's dependency closure",
            ),
            [(f.rule, f.task, f.evidence) for f in result.findings],
        )

    def test_a_creator_outside_the_closure_is_reported(self):
        result = run("neg_registrar_unreachable.md")

        self.assertIn(
            (
                "creator-outside-closure",
                "AAA-4",
                "-R t0_late needs AAA-5, which creates `tests/t0_late.cpp`; "
                "AAA-5 is not in AAA-4's dependency closure",
            ),
            [(f.rule, f.task, f.evidence) for f in result.findings],
        )

    def test_the_clean_shape_and_the_self_registering_task_are_not_reported(self):
        result = run("neg_registrar_unreachable.md")

        self.assertEqual(
            sorted((f.rule, f.task) for f in result.findings),
            # AAA-4's registrar AAA-3 IS reachable; only its creator AAA-5 is not.
            [
                ("creator-outside-closure", "AAA-4"),
                ("registrar-outside-closure", "AAA-1"),
            ],
        )

    def test_a_name_with_no_creator_at_all_is_reported_separately(self):
        doc = PlanDocument.from_text(
            "**AAA-1 · A task** — T0\n"
            "Files: `src/one.cpp`\n"
            "Depends: none\n"
            "Check: `ctest --test-dir build --no-tests=error -R t0_ghost`.\n",
            name="inline",
        )

        self.assertEqual(
            [(f.rule, f.task, f.evidence) for f in registrar.run(doc).findings],
            [
                (
                    "registrar-unknown",
                    "AAA-1",
                    "-R t0_ghost; no `Files:` line creates a source or a target "
                    "for that name",
                )
            ],
        )

    def test_a_document_with_no_ctest_invocation_is_a_hard_error(self):
        result = registrar.run(
            PlanDocument.from_text(
                "**AAA-1 · A task** — T0\n"
                "Files: `src/one.cpp`\n"
                "Depends: none\n"
                "Check: The operator confirms it.\n",
                name="inline",
            )
        )

        self.assertEqual(
            [(f.rule, f.message) for f in result.findings],
            [("no-input", "the registrar lint examined 0 `-R` arguments")],
        )


class AbbreviatedPathRegistrarTest(unittest.TestCase):
    """The registrar blind spot that section 1.1.1 rule B closes.

    BBB-1 writes `g2Lib/test/t0_short.cpp` and AAA-1 owns
    `source/nord/g2/g2Lib/test/CMakeLists.txt`. **The two spellings name one
    directory.** Without the expansion the lint sees two unrelated directories,
    finds no registrar for BBB-1 at all, and reports clean.
    """

    def test_an_abbreviated_writer_reports_its_unreachable_registrar(self):
        result = run("neg_path_abbreviation.md")
        found = [
            f
            for f in result.findings
            if f.rule == "registrar-outside-closure" and f.task == "BBB-1"
        ]
        self.assertEqual(len(found), 1)
        self.assertIn("AAA-1", found[0].evidence)
        self.assertIn("source/nord/g2/g2Lib/test/CMakeLists.txt", found[0].evidence)

    def test_a_writer_that_declares_the_registrar_is_clean(self):
        result = run("neg_path_abbreviation.md")

        # Before the path expansion this fixture reported clean, thus an empty
        # finding list is the pre-repair behaviour. The pin below keeps this
        # test from passing in that state.
        self.assertEqual([f.task for f in result.findings], ["BBB-1"])
        self.assertEqual(
            [f for f in result.findings if f.task in {"CCC-1", "DDD-1", "EEE-1"}], []
        )


class OwnerAgainstLaterWriterTest(unittest.TestCase):
    """Section 7.4.2 names an OWNER for a registration list, and it calls every
    other task that writes the list a DECLARED SECOND WRITER.

    The registration rule of that section obliges a task whose check runs
    `ctest -R <name>` to declare, on its own `Files:` line, the list it edits to
    register that name. **A registration is a change, and a change is
    declared.** The lint read every declarer of the list as a CREATOR of it, so
    the compliant line made each writer a registrar the other writers had to
    reach — and the form the document requires was the form the lint rejected.

    Adding the registration list to a task's `Files:` line, which is exactly
    what section 7.4.2 asks of it, therefore turned the plan red under the old
    reading.

    The rule is not weakened to clear that: the OWNER must still be reachable,
    and `UnreachableOwner` below is the direction that must keep failing.
    """

    OWNED = (
        "### 7.4.2 Every shared file has one owner\n"
        "\n"
        "| Path | Owner |\n"
        "|---|---|\n"
        "| `alpha/test/CMakeLists.txt` | **AAA-0** |\n"
        "\n"
        "## 9. The tasks\n"
        "\n"
        "**AAA-0 · The registrar, which creates the list and registers nothing** — T0\n"
        "Files: `alpha/test/CMakeLists.txt`\n"
        "Design: 1\n"
        "Depends: none\n"
        "Check: `cmake -S . -B build` succeeds and the configured tree holds "
        "`build/alpha/test/CTestTestfile.cmake`.\n"
        "\n"
        "**BBB-1 · The first declared second writer** — T0\n"
        "Files: `alpha/test/CMakeLists.txt`, `alpha/test/t0_beta.cpp`\n"
        "Design: 2\n"
        "Depends: AAA-0\n"
        "Check: `ctest --test-dir build --no-tests=error -R ^t0_beta$`. "
        "Registered with `add_test(NAME t0_beta ...)`.\n"
        "\n"
        "**CCC-1 · The second declared second writer** — T0\n"
        "Files: `alpha/test/CMakeLists.txt`, `alpha/test/t0_gamma.cpp`\n"
        "Design: 3\n"
        "Depends: AAA-0\n"
        "Check: `ctest --test-dir build --no-tests=error -R ^t0_gamma$`. "
        "Registered with `add_test(NAME t0_gamma ...)`.\n"
    )

    # The same writers, and DDD-1 reaches the owner through nothing at
    # all. Its `Files:` line carries the registration the rule asks for, so the
    # only thing between it and a passing check is AAA-0, which it never waits
    # on.
    UNREACHABLE_OWNER = OWNED + (
        "\n"
        "**DDD-1 · The writer that never waits on the owner** — T0\n"
        "Files: `alpha/test/CMakeLists.txt`, `alpha/test/t0_delta.cpp`\n"
        "Design: 4\n"
        "Depends: none\n"
        "Check: `ctest --test-dir build --no-tests=error -R ^t0_delta$`. "
        "Registered with `add_test(NAME t0_delta ...)`.\n"
    )

    def owned(self):
        return PlanDocument.from_text(self.OWNED, name="inline")

    def unreachable_owner(self):
        return PlanDocument.from_text(self.UNREACHABLE_OWNER, name="inline")

    def test_the_owner_alone_registers_the_directory(self):
        """`registrars_of` answers with the task section 7.4.2 names, and not
        with the two later writers that declare the same list."""
        self.assertEqual(
            [
                (task.ident, cmake)
                for task, cmake in registrar.registrars_of(
                    self.owned(), "alpha/test/t0_beta.cpp"
                )
            ],
            [("AAA-0", "alpha/test/CMakeLists.txt")],
        )

    def test_two_declared_second_writers_do_not_register_each_other(self):
        """BBB-1 and CCC-1 both declare the list, neither declares the other,
        and both reach the owner. This is the compliant form of section 7.4.2's
        registration rule, and it must report nothing."""
        self.assertEqual(registrar.run(self.owned()).findings, [])

    def test_the_compliant_form_examines_both_names(self):
        """An empty examination would make the assertion above pass while
        reading nothing at all."""
        self.assertEqual(registrar.run(self.owned()).examined, 2)

    def test_a_writer_that_cannot_reach_the_owner_is_still_an_error(self):
        """The direction the repair must NOT weaken. Exactly one finding, and
        it names the owner — not the other writers of the same list."""
        self.assertEqual(
            [
                (f.rule, f.task, f.severity, f.evidence)
                for f in registrar.run(self.unreachable_owner()).findings
            ],
            [
                (
                    "registrar-outside-closure",
                    "DDD-1",
                    ERROR,
                    "-R t0_delta needs AAA-0, which creates "
                    "`alpha/test/CMakeLists.txt`; AAA-0 is not in DDD-1's "
                    "dependency closure",
                )
            ],
        )

    def test_a_list_with_no_owner_row_still_reads_every_declarer(self):
        """Section 7.4.2 names an owner for every shared registration list, and
        `shared-path-without-owner` is the ERROR when it does not. Where the
        document states no owner the lint cannot tell the creator from the
        writers, so it keeps the conservative reading and suspects them all —
        the repair narrows the rule where the document speaks, nowhere else.
        """
        doc = PlanDocument.from_text(
            self.OWNED.replace("| `alpha/test/CMakeLists.txt` | **AAA-0** |\n", ""),
            name="inline",
        )

        self.assertEqual(
            [
                (task.ident, cmake)
                for task, cmake in registrar.registrars_of(
                    doc, "alpha/test/t0_beta.cpp"
                )
            ],
            [
                ("AAA-0", "alpha/test/CMakeLists.txt"),
                ("BBB-1", "alpha/test/CMakeLists.txt"),
                ("CCC-1", "alpha/test/CMakeLists.txt"),
            ],
        )

    def test_an_owner_cell_naming_no_task_falls_back_to_every_declarer(self):
        """Section 7.4.2 carries prose owners — `the plugin track`, `the
        operator`. A cell that names no task block states no registrar, so the
        conservative reading stands rather than an owner list of one None."""
        doc = PlanDocument.from_text(
            self.OWNED.replace("| **AAA-0** |", "| **the alpha track** |"),
            name="inline",
        )

        self.assertEqual(
            [
                task.ident
                for task, _ in registrar.registrars_of(doc, "alpha/test/t0_beta.cpp")
            ],
            ["AAA-0", "BBB-1", "CCC-1"],
        )

    def test_the_second_writer_named_beside_the_owner_does_not_register(self):
        """The BRD-0/BRD-23 shape, verbatim from section 7.4.2: `**DSP-0**, with
        **DSP-1** as the one declared second writer`. The FIRST identifier in
        the cell is the owner; every later one is a declared second writer and
        registers nothing."""
        doc = PlanDocument.from_text(
            self.OWNED.replace(
                "| **AAA-0** |",
                "| **AAA-0**, with **CCC-1** as the one declared second writer |",
            ),
            name="inline",
        )

        self.assertEqual(
            [
                (task.ident, cmake)
                for task, cmake in registrar.registrars_of(
                    doc, "alpha/test/t0_beta.cpp"
                )
            ],
            [("AAA-0", "alpha/test/CMakeLists.txt")],
        )


class MarkedSecondWriteTest(unittest.TestCase):
    """Section 1.1.1 rule D: a MARKED `Files:` entry is not a claim of
    ownership.

    `<path>@<OWNER-ID>` says the file belongs to `<OWNER-ID>` and that this task
    only changes it. The creator lookup compared the marked spelling as written
    and matched on the stem anyway — `t0_beta.cpp@BBB-1` splits at the LAST dot
    — so the second writer was read as the task that CREATES the source, and
    the owner was then reported for not reaching its own second writer.

    The repair a reader reaches for is to drop the marker, and it is wrong
    twice: section 7.6 assertion 8 REQUIRES the marker on a second writer, and
    an unmarked pair is two bare claimants, which section 7.4.2 condition 10
    classes as the worse defect. The artifact is right and the signal is wrong.

    Both directions are asserted. `has_marker` is what excuses the entry, so an
    entry that carries NO marker is still a creation and still has to be
    reachable — otherwise this trades a false positive for a false negative,
    and the second class is the one nobody sees.
    """

    MARKED = (
        "### 7.4.2 Every shared file has one owner\n"
        "\n"
        "| Path | Owner |\n"
        "|---|---|\n"
        "| `alpha/test/CMakeLists.txt` | **AAA-0** |\n"
        "| `alpha/test/t0_beta.cpp` | **BBB-1** |\n"
        "\n"
        "## 9. The tasks\n"
        "\n"
        "**AAA-0 · The registrar** — T0\n"
        "Files: `alpha/test/CMakeLists.txt`\n"
        "Design: 1\n"
        "Depends: none\n"
        "Check: `cmake -S . -B build` succeeds and the configured tree holds "
        "`build/alpha/test/CTestTestfile.cmake`.\n"
        "\n"
        "**BBB-1 · The owner of the test source** — T0\n"
        "Files: `alpha/test/CMakeLists.txt`, `alpha/test/t0_beta.cpp`\n"
        "Design: 2\n"
        "Depends: AAA-0\n"
        "Check: `ctest --test-dir build --no-tests=error -R ^t0_beta$`. "
        "Registered with `add_test(NAME t0_beta ...)`.\n"
        "\n"
        "**CCC-1 · The declared second writer of that source** — T0\n"
        "Files: `alpha/test/CMakeLists.txt`, `alpha/test/t0_gamma.cpp`, "
        "`alpha/test/t0_beta.cpp@BBB-1`\n"
        "Design: 3\n"
        "Depends: AAA-0, BBB-1\n"
        "Check: `ctest --test-dir build --no-tests=error -R ^t0_gamma$`. "
        "Registered with `add_test(NAME t0_gamma ...)`.\n"
    )

    # The one character that carries rule D, removed. Nothing else moves, so
    # the marker is the only thing the pair of documents differs by.
    UNMARKED = MARKED.replace(
        "`alpha/test/t0_beta.cpp@BBB-1`", "`alpha/test/t0_beta.cpp`"
    )

    def marked(self):
        return PlanDocument.from_text(self.MARKED, name="inline")

    def unmarked(self):
        return PlanDocument.from_text(self.UNMARKED, name="inline")

    def test_a_marked_entry_creates_nothing(self):
        self.assertEqual(
            [
                (task.ident, item)
                for task, item in registrar.creators_of(self.marked(), "t0_beta")
            ],
            [("BBB-1", "alpha/test/t0_beta.cpp")],
        )

    def test_the_owner_is_not_reported_for_failing_to_reach_its_second_writer(self):
        self.assertEqual(registrar.run(self.marked()).findings, [])

    def test_the_marked_document_examines_both_names(self):
        """An empty examination would make the assertion above pass while
        reading nothing at all."""
        self.assertEqual(registrar.run(self.marked()).examined, 2)

    def test_an_unmarked_second_write_is_still_a_creation(self):
        self.assertEqual(
            [
                (task.ident, item)
                for task, item in registrar.creators_of(self.unmarked(), "t0_beta")
            ],
            [("BBB-1", "alpha/test/t0_beta.cpp"), ("CCC-1", "alpha/test/t0_beta.cpp")],
        )

    def test_an_unmarked_second_write_outside_the_closure_is_still_reported(self):
        self.assertEqual(
            [
                (f.rule, f.task, f.severity, f.evidence)
                for f in registrar.run(self.unmarked()).findings
            ],
            [
                (
                    "creator-outside-closure",
                    "BBB-1",
                    ERROR,
                    "-R t0_beta needs CCC-1, which creates "
                    "`alpha/test/t0_beta.cpp`; CCC-1 is not in BBB-1's "
                    "dependency closure",
                )
            ],
        )


if __name__ == "__main__":
    unittest.main()
