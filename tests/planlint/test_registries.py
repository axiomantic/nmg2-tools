"""Tests for the check-target registry lint.

Every case is a RED proof first: build the input the author knows is bad,
assert the finding, then remove exactly the defect and assert the finding is
gone. A check that has never gone red for a condition is not evidence that it
sees the condition.

The repositories are synthetic. A real tree is a moving target, and a lint that
passes only against today's `mcf5307` proves nothing about the mechanism.
"""

import os
import pathlib
import stat
import tempfile
import unittest

from planlint import checks, registries
from planlint.document import PlanDocument
from planlint.finding import ERROR, WARNING


def rules_of(result):
    return sorted(f.rule for f in result.findings)


def by_rule(result, rule):
    return [f for f in result.findings if f.rule == rule]


# One complete task (`AAA-1`, anchored `**DONE`) and one that has not run
# (`AAA-2`). The pair is what separates the two severities.
PLAN = (
    "**AAA-1 · The shipped one** — T0\n"
    "Files: `alpha/test/t0_alpha.cpp`, `alpha/test/tests_alpha.cmake`\n"
    "Design: 1\n"
    "Depends: none\n"
    "**DONE on 2026-01-01, 1 commit.**\n"
    "Check: `ctest --test-dir build --no-tests=error -R ^t0_alpha$`.\n"
    "\n"
    "**AAA-2 · The unbuilt one** — T0\n"
    "Files: `alpha/test/t0_beta.cpp`, `alpha/test/tests_alpha.cmake@AAA-1`\n"
    "Design: 1\n"
    "Depends: AAA-1\n"
    "Check: `ctest --test-dir build --no-tests=error -R ^t0_beta$`.\n"
)


def write_repo(root, registrations, extra=()):
    """A repository that registers exactly `registrations`."""
    root = pathlib.Path(root)
    (root / "alpha" / "test").mkdir(parents=True, exist_ok=True)
    body = "\n".join(f"add_test(NAME {name} COMMAND {name})" for name in registrations)
    (root / "alpha" / "test" / "tests_alpha.cmake").write_text(body + "\n")
    for relative in extra:
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("")
    return root


class GreenBaselineTest(unittest.TestCase):
    """The control. Without it the red cases below say nothing: a lint that
    reports a finding on every input has not discriminated anything."""

    def test_a_registered_target_produces_no_finding(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_repo(tmp, ["t0_alpha", "t0_beta"])
            result = registries.run(PlanDocument.from_text(PLAN), {"alpha": tmp})
        self.assertEqual(result.findings, [])
        self.assertEqual(result.examined, 2)


class UnregisteredTest(unittest.TestCase):
    def test_a_complete_task_whose_name_nothing_registers_is_an_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_repo(tmp, ["t0_beta"])
            result = registries.run(PlanDocument.from_text(PLAN), {"alpha": tmp})
        found = by_rule(result, "registry-target-unregistered")
        self.assertEqual([f.severity for f in found], [ERROR])
        self.assertEqual(found[0].task, "AAA-1")
        self.assertIn("t0_alpha", found[0].evidence)

    def test_an_incomplete_task_is_a_warning_and_not_an_error(self):
        """Most of the plan is unbuilt. A lint red on day one gets turned off."""
        with tempfile.TemporaryDirectory() as tmp:
            write_repo(tmp, ["t0_alpha"])
            result = registries.run(PlanDocument.from_text(PLAN), {"alpha": tmp})
        found = by_rule(result, "registry-target-unregistered")
        self.assertEqual([f.severity for f in found], [WARNING])
        self.assertEqual(found[0].task, "AAA-2")

    def test_the_name_is_found_in_any_searched_repository_not_only_its_own(self):
        """The lint asks whether a target is runnable ANYWHERE, because the
        plan carries no usable repository attribution. A name registered in the
        second tree is registered."""
        with tempfile.TemporaryDirectory() as one, tempfile.TemporaryDirectory() as two:
            write_repo(one, ["t0_beta"])
            write_repo(two, ["t0_alpha"])
            result = registries.run(
                PlanDocument.from_text(PLAN), {"one": one, "two": two}
            )
        self.assertEqual(result.findings, [])

    def test_a_wrapper_registration_is_resolved_and_not_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = write_repo(tmp, ["t0_beta"])
            (root / "alpha" / "test" / "wrap.cmake").write_text(
                "function(alpha_add_test _name)\n"
                "    add_test(NAME ${_name} COMMAND ${_name})\n"
                "endfunction()\n"
                "alpha_add_test(t0_alpha)\n"
            )
            result = registries.run(PlanDocument.from_text(PLAN), {"alpha": tmp})
        self.assertEqual(result.findings, [])

    def test_a_build_tree_registration_does_not_count(self):
        """A generated `CTestTestfile.cmake` would make the answer depend on
        whether somebody had configured the tree."""
        with tempfile.TemporaryDirectory() as tmp:
            root = write_repo(tmp, ["t0_beta"])
            (root / "build" / "alpha").mkdir(parents=True)
            (root / "build" / "alpha" / "CTestTestfile.cmake").write_text(
                "add_test(NAME t0_alpha COMMAND t0_alpha)\n"
            )
            result = registries.run(PlanDocument.from_text(PLAN), {"alpha": tmp})
        self.assertEqual(rules_of(result), ["registry-target-unregistered"])


class PlaceholderTest(unittest.TestCase):
    PROSE = PLAN.replace(
        "`ctest --test-dir build --no-tests=error -R ^t0_beta$`",
        "`pytest tests/…`",
    )

    def test_a_prose_placeholder_is_an_error_whatever_its_owner_state(self):
        """`AAA-2` is NOT complete, so the completion-scoped severity would make
        this a warning. No amount of later work makes `pytest tests/…` run."""
        with tempfile.TemporaryDirectory() as tmp:
            write_repo(tmp, ["t0_alpha"])
            result = registries.run(PlanDocument.from_text(self.PROSE), {"alpha": tmp})
        found = by_rule(result, "registry-target-is-placeholder")
        self.assertEqual([f.severity for f in found], [ERROR])
        self.assertIn("pytest tests/…", found[0].evidence)

    def test_the_metavariable_spelling_is_caught_too(self):
        text = self.PROSE.replace("pytest tests/…", "pytest <path>")
        with tempfile.TemporaryDirectory() as tmp:
            write_repo(tmp, ["t0_alpha"])
            result = registries.run(PlanDocument.from_text(text), {"alpha": tmp})
        self.assertEqual(rules_of(result), ["registry-target-is-placeholder"])


class PytestPathTest(unittest.TestCase):
    TEXT = PLAN.replace(
        "`ctest --test-dir build --no-tests=error -R ^t0_alpha$`",
        "`pytest tests/test_alpha.py`",
    )

    def test_a_pytest_path_that_exists_nowhere_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_repo(tmp, ["t0_beta"])
            result = registries.run(PlanDocument.from_text(self.TEXT), {"alpha": tmp})
        found = by_rule(result, "registry-pytest-path-missing")
        self.assertEqual([f.severity for f in found], [ERROR])

    def test_the_finding_disappears_when_the_file_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_repo(tmp, ["t0_beta"], extra=["tests/test_alpha.py"])
            result = registries.run(PlanDocument.from_text(self.TEXT), {"alpha": tmp})
        self.assertEqual(result.findings, [])


class LoudFailureTest(unittest.TestCase):
    """A repository this lint cannot read must never read as clean, and an
    absence from an incomplete search must never be spelled like a decided no."""

    def test_no_repository_at_all_is_an_error_and_never_a_clean_run(self):
        result = registries.run(PlanDocument.from_text(PLAN), None)
        self.assertIn("registry-not-searched", rules_of(result))
        self.assertTrue(result.failed)

    def test_a_root_that_is_not_a_directory_is_an_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = registries.run(
                PlanDocument.from_text(PLAN),
                {"alpha": str(pathlib.Path(tmp) / "absent")},
            )
        self.assertIn("registry-unreadable", rules_of(result))

    def test_an_unreadable_cmake_file_makes_every_absence_unresolved(self):
        """Not `unregistered`. The two demand different repairs, and one
        message for both sends the reader to the wrong one."""
        if os.geteuid() == 0:
            self.skipTest("root reads a mode-000 file, so the plant cannot fire")
        with tempfile.TemporaryDirectory() as tmp:
            root = write_repo(tmp, ["t0_beta"])
            blocked = root / "alpha" / "test" / "blocked.cmake"
            blocked.write_text("add_test(NAME t0_alpha COMMAND t0_alpha)\n")
            blocked.chmod(0)
            try:
                result = registries.run(PlanDocument.from_text(PLAN), {"alpha": tmp})
            finally:
                blocked.chmod(stat.S_IRUSR | stat.S_IWUSR)
        self.assertEqual(
            rules_of(result),
            ["registry-target-unresolved", "registry-unreadable"],
        )
        self.assertNotIn(
            "registry-target-unregistered", rules_of(result)
        )
        self.assertIn("INCOMPLETE", result.notice)

    def test_a_registry_that_holds_nothing_is_reported_as_a_broken_search(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_repo(tmp, [])
            result = registries.run(PlanDocument.from_text(PLAN), {"alpha": tmp})
        self.assertIn("registry-empty", rules_of(result))

    def test_the_notice_names_every_tree_and_its_contribution(self):
        """A tree silently dropped from the search is visible on a CLEAN run
        and not only on a dirty one."""
        with tempfile.TemporaryDirectory() as one, tempfile.TemporaryDirectory() as two:
            write_repo(one, ["t0_alpha"])
            write_repo(two, ["t0_beta"])
            result = registries.run(
                PlanDocument.from_text(PLAN), {"one": one, "two": two}
            )
        self.assertEqual(result.findings, [])
        self.assertIn("one:", result.notice)
        self.assertIn("two:", result.notice)
        self.assertIn("complete", result.notice)
        self.assertIn("never a `ctest` listing", result.notice)

    def test_a_plan_with_no_check_target_is_a_hard_error(self):
        text = "**AAA-1 · No check** — T0\nFiles: `a.cpp`\nDesign: 1\nDepends: none\n"
        with tempfile.TemporaryDirectory() as tmp:
            write_repo(tmp, ["t0_alpha"])
            result = registries.run(PlanDocument.from_text(text), {"alpha": tmp})
        self.assertIn("no-input", rules_of(result))


class OneExtractorTest(unittest.TestCase):
    """The roster comparison and this lint read the plan through ONE function.
    Two extractors would let the pair disagree about what the plan says while
    both reported clean."""

    def test_the_target_set_is_the_one_the_roster_comparison_uses(self):
        doc = PlanDocument.from_text(PLAN)
        self.assertEqual(set(checks.target_origins(doc)), {"t0_alpha", "t0_beta"})

    def test_the_origins_carry_the_owning_task(self):
        doc = PlanDocument.from_text(PLAN)
        self.assertEqual(
            registries.owners_of(checks.target_origins(doc)["t0_alpha"]), ["AAA-1"]
        )

    def test_only_an_anchored_done_marker_counts_as_complete(self):
        doc = PlanDocument.from_text(PLAN)
        self.assertEqual(registries.complete_tasks(doc), {"AAA-1"})


if __name__ == "__main__":
    unittest.main()
