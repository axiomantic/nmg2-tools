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
    """`creator_of()` returned the FIRST basename match in document order and
    ignored the directory, so with two same-named test files the second was
    invisible and the verdict depended on file position. The registrar half
    already returned a list; the creator half returns one too, and every
    candidate must be reachable — the lint cannot tell which source the name
    resolves to, so it may excuse none of them.
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
        # Seven `-R` arguments, one per task check that runs `ctest`. DDD-1 runs
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
    directory.** Before the expansion the lint saw two unrelated directories,
    found no registrar for BBB-1 at all, and reported clean — while 34 tasks in
    the real plan sat in exactly that shape.
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


if __name__ == "__main__":
    unittest.main()
