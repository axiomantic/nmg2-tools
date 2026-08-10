"""Tests for the section 1.3 rule 9 lint.

Every test here is a RED proof first. A check is evidence only after it has gone
red on input the author knew was bad, so each case builds the bad input, asserts
the finding, then removes exactly the defect and asserts the finding is gone.

The half-B cases build a synthetic repository rather than reading a real one,
because a real tree is a moving target and a lint that passes only against
today's tree proves nothing about the mechanism.
"""

import pathlib
import tempfile
import unittest

from planlint import rule9
from planlint.document import PlanDocument
from planlint.finding import ERROR


def rules_of(result):
    return sorted(f.rule for f in result.findings)


def plan(text):
    return PlanDocument.from_text(text)


COMPLIANT = (
    "**AAA-1 · The registrar** — T0\n"
    "Files: `alpha/test/CMakeLists.txt`, `alpha/test/tests_alpha.cmake`\n"
    "Design: 1\n"
    "Depends: none\n"
    "Check: `ctest --test-dir build --no-tests=error -N` lists `Total Tests: 0`.\n"
    "\n"
    "**AAA-2 · The carrier** — T0\n"
    "Files: `alpha/alpha.cpp`, `alpha/test/t0_alpha.cpp`, "
    "`alpha/test/tests_alpha.cmake@AAA-1`\n"
    "Design: 1\n"
    "Depends: AAA-1\n"
    "Check: `ctest --test-dir build --no-tests=error -R ^t0_alpha$`.\n"
)

# The same plan with the registration list struck from AAA-2's `Files:` line.
# This is BRD-21's shape exactly: a header, a source and a test, and no list.
NO_LIST = COMPLIANT.replace(", `alpha/test/tests_alpha.cmake@AAA-1`", "")

# The same plan with a `-R` name no `Files:` line creates.
NOT_CREATED = COMPLIANT.replace("^t0_alpha$", "^t0_absent$")


class RegistrationListShapeTest(unittest.TestCase):
    """Section 7.4.2 states the registration lists as a CLASS, so the predicate
    reads a shape and never a roster. A roster needs an edit per repository."""

    def test_the_three_stated_shapes_are_registration_lists(self):
        for item in (
            "source/nord/g2/g2Lib/test/tests_board.cmake",
            "tests/tests_cpu.cmake",
            "conformance/conformance_cpu.cmake",
            "source/dsp56kEmu/test/CMakeLists.txt",
        ):
            self.assertTrue(rule9.is_registration_list(item), item)

    def test_the_owner_marker_is_split_off_before_the_path_is_read(self):
        self.assertTrue(
            rule9.is_registration_list(
                "source/nord/g2/g2Lib/test/tests_board.cmake@BRD-0"
            )
        )

    def test_a_source_list_is_not_a_registration_list(self):
        """`sources_board.cmake` registers no test. Accepting it would let a
        task satisfy clause 2 by naming the file that compiles the code."""
        self.assertFalse(
            rule9.is_registration_list("source/nord/g2/g2Lib/sources_board.cmake")
        )

    def test_a_root_cmakelists_is_not_a_registration_list(self):
        self.assertFalse(rule9.is_registration_list("CMakeLists.txt"))
        self.assertFalse(rule9.is_registration_list("alpha/CMakeLists.txt"))


class HalfATest(unittest.TestCase):
    def test_a_task_naming_no_registration_list_is_reported(self):
        result = rule9.run(plan(NO_LIST))

        self.assertEqual(rules_of(result), ["rule9a-no-registration-list"])
        self.assertEqual(result.findings[0].task, "AAA-2")
        self.assertEqual(result.findings[0].severity, ERROR)

    def test_restoring_the_registration_list_clears_the_finding(self):
        self.assertEqual(rule9.run(plan(COMPLIANT)).findings, [])

    def test_a_name_no_files_line_creates_is_reported(self):
        result = rule9.run(plan(NOT_CREATED))

        self.assertIn("rule9a-name-not-created", rules_of(result))

    def test_a_creator_elsewhere_may_carry_the_list(self):
        """Rule 9 binds "that task" — the one whose `Files:` line names the
        source. When the creator declares the list, the checking task is clean
        even though it names none itself."""
        text = COMPLIANT.replace(
            "Files: `alpha/alpha.cpp`, `alpha/test/t0_alpha.cpp`, "
            "`alpha/test/tests_alpha.cmake@AAA-1`",
            "Files: `alpha/alpha.cpp`",
        ).replace(
            "Files: `alpha/test/CMakeLists.txt`, `alpha/test/tests_alpha.cmake`",
            "Files: `alpha/test/CMakeLists.txt`, `alpha/test/tests_alpha.cmake`, "
            "`alpha/test/t0_alpha.cpp`",
        )

        self.assertEqual(rule9.run(plan(text)).findings, [])

    def test_a_prefix_allow_list_argument_is_not_a_registered_name(self):
        """Section 7.7 allow-lists two `-R` arguments that are prefixes. Neither
        is a registered name, so neither is rule 9's subject — and with nothing
        else left to examine the lint reports `no-input` rather than a pass."""
        text = COMPLIANT.replace("^t0_alpha$", "t1_")
        result = rule9.run(plan(text))

        self.assertEqual(rules_of(result), ["no-input"])

    def test_no_r_argument_anywhere_is_a_hard_error_and_never_a_pass(self):
        text = COMPLIANT.replace(
            "`ctest --test-dir build --no-tests=error -R ^t0_alpha$`",
            "the build succeeds",
        )
        result = rule9.run(plan(text))

        self.assertIn("no-input", rules_of(result))


class RegisteredNamesTest(unittest.TestCase):
    """`add_test(NAME <name>)` is not the only registration form, and a lint
    that reads only the literal one reports a false alarm the size of the real
    finding. `source/dsp56kEmu/test/CMakeLists.txt` registers seven names
    through a wrapper function."""

    def test_the_literal_form_is_read(self):
        with tempfile.TemporaryDirectory() as root:
            path = pathlib.Path(root) / "tests_alpha.cmake"
            path.write_text("add_test(NAME t0_alpha COMMAND t0_alpha)\n")

            self.assertEqual(rule9.registered_names(root), {"t0_alpha"})

    def test_a_wrapper_function_is_resolved(self):
        with tempfile.TemporaryDirectory() as root:
            path = pathlib.Path(root) / "CMakeLists.txt"
            path.write_text(
                "function(alpha_add_test _name)\n"
                "\tadd_executable(${_name} ${_name}.cpp)\n"
                "\tadd_test(NAME ${_name} COMMAND ${_name})\n"
                "endfunction()\n"
                "\n"
                "alpha_add_test(t0_alpha)\t# AAA-2\n"
                "alpha_add_test(t0_beta)\n"
            )

            self.assertEqual(rule9.registered_names(root), {"t0_alpha", "t0_beta"})

    def test_a_wrapper_that_registers_nothing_registers_nothing(self):
        """A function that only builds an executable is not a registration, and
        reading its calls as registrations would excuse the whole defect."""
        with tempfile.TemporaryDirectory() as root:
            path = pathlib.Path(root) / "CMakeLists.txt"
            path.write_text(
                "function(alpha_add_program _name)\n"
                "\tadd_executable(${_name} ${_name}.cpp)\n"
                "endfunction()\n"
                "alpha_add_program(t0_alpha)\n"
            )

            self.assertEqual(rule9.registered_names(root), set())


class HalfBTest(unittest.TestCase):
    """The half that catches BRD-21: the source shipped and the registration
    did not."""

    def build(self, register):
        root = pathlib.Path(self.root)
        test_dir = root / "alpha" / "test"
        test_dir.mkdir(parents=True)
        (test_dir / "t0_alpha.cpp").write_text("int main() { return 0; }\n")
        (test_dir / "tests_alpha.cmake").write_text(
            "add_test(NAME t0_alpha COMMAND t0_alpha)\n" if register else "# empty\n"
        )
        return {"alpha": root}

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = self._tmp.name
        self.addCleanup(self._tmp.cleanup)

    def test_a_shipped_source_with_no_registration_is_reported(self):
        result = rule9.run(plan(COMPLIANT), source_repos=self.build(register=False))

        self.assertEqual(rules_of(result), ["rule9b-not-registered"])
        self.assertEqual(result.findings[0].task, "AAA-2")
        self.assertIn("t0_alpha", result.findings[0].evidence)

    def test_adding_the_registration_clears_the_finding(self):
        result = rule9.run(plan(COMPLIANT), source_repos=self.build(register=True))

        self.assertEqual(result.findings, [])

    def test_an_unbuilt_task_is_not_a_violation(self):
        """Most of this plan is unwritten. A half that reported every unbuilt
        test would be red before any work was done, and a lint that is red on
        day one is a lint an engineer turns off."""
        root = pathlib.Path(self.root)
        (root / "alpha").mkdir()

        result = rule9.run(plan(COMPLIANT), source_repos={"alpha": root})

        self.assertEqual(result.findings, [])

    def test_a_declared_check_target_is_a_completion_signal_of_its_own(self):
        """`docs/check-targets.txt` states its own rule: it declares the
        targets of the tasks declared complete and no others. A name it carries
        belongs to a task that shipped, whether or not the source path in the
        plan resolves."""
        root = pathlib.Path(self.root)
        docs = root / "docs"
        docs.mkdir()
        docs.write_text  # noqa: B018 - directory, not a file
        (docs / "check-targets.txt").write_text("# a comment\nt0_alpha\n")

        result = rule9.run(plan(COMPLIANT), source_repos={"alpha": root})

        self.assertEqual(rules_of(result), ["rule9b-not-registered"])

    def test_half_b_is_silent_when_no_repository_is_given(self):
        self.assertEqual(rule9.run(plan(COMPLIANT)).findings, [])


if __name__ == "__main__":
    unittest.main()
