"""Tests about the test suite itself.

A suite that silently drops tests is the same defect class as a check that
cannot fail. Two ways were measured:

  * a class appended BELOW `if __name__ == "__main__": unittest.main()` runs
    under `pytest` and under `unittest discover`, and is skipped when the file
    is run directly. Thirteen tests were in that position, and they were exactly
    the tests that pin the path-expansion edit;
  * a fixture with no row in the README table is a fixture a reader cannot find,
    under a heading that reads "A lint with no negative fixture is not done".

Both are asserted here mechanically, so neither can reopen.
"""

import ast
import os
import pathlib
import unittest

TESTS = pathlib.Path(__file__).resolve().parent
FIXTURES = TESTS / "fixtures"
# This suite sits at `tests/planlint/` and the package it tests sits at
# `planlint/` in the repository root. `ROOT` is that root, and the README that
# carries the fixture table is the one beside the package, not the README of
# the repository.
ROOT = TESTS.parents[1]
README = ROOT / "planlint" / "README.md"


def discover_test_modules():
    """Every test module in this directory, sorted by path.

    The name of this helper started with `test_`, so `pytest` collected it as
    a test. It returned a value and asserted nothing, thus it could not fail.
    `TestModuleDiscoveryTest` below now asserts what the callers need.
    """
    return sorted(p for p in TESTS.glob("test_*.py"))


def collected_tests(tree):
    """Every function that a runner collects as a test.

    `pytest` collects a module-level function whose name starts with `test`.
    Both runners collect a method whose name starts with `test`.
    """
    found = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name.startswith("test"):
                found.append((None, node))
        elif isinstance(node, ast.ClassDef):
            for member in node.body:
                if not isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                if member.name.startswith("test"):
                    found.append((node.name, member))
    return found


def returned_values(function):
    """Every `return <value>` statement in the body of a function.

    A function or a class that is nested in the body is not examined. Its
    `return` belongs to the nested function, not to the test.
    """
    found = []
    pending = list(function.body)
    while pending:
        node = pending.pop()
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
            continue
        if isinstance(node, ast.Return) and node.value is not None:
            found.append(node)
        pending.extend(ast.iter_child_nodes(node))
    return found


def carries_guard(path):
    """True if the module has a real `if __name__ == "__main__":` statement.

    A text search is not sufficient. The docstring of this module speaks about
    the guard, thus a text search finds `__main__` even if the guard is absent.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.If) and ast.unparse(node.test) == "__name__ == '__main__'":
            return True
    return False


def qualified_names(path):
    """The name of every collected test in one module, as `module.Class.method`."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names = []
    for owner, function in collected_tests(tree):
        parts = [path.stem, owner, function.name] if owner else [path.stem, function.name]
        names.append(".".join(parts))
    return names


def loaded_names():
    """The name of every test that the `unittest` loader runs."""
    # `top_level_dir` is the repository ROOT and not `tests/`. Discovery from
    # `tests/` would name these modules `planlint.test_x` and would put
    # `tests/` first on `sys.path`, so `tests/planlint/` would shadow the
    # `planlint` package this suite tests. From the root the names are
    # `tests.planlint.test_x` and no shadow is possible.
    suite = unittest.TestLoader().discover(str(TESTS), top_level_dir=str(ROOT))
    names = []
    pending = [suite]
    while pending:
        item = pending.pop()
        if isinstance(item, unittest.TestSuite):
            pending.extend(item)
            continue
        module = type(item).__module__.rsplit(".", 1)[-1]
        names.append(f"{module}.{type(item).__name__}.{item._testMethodName}")
    return names


class MainGuardPositionTest(unittest.TestCase):
    """The `unittest.main()` guard runs the tests defined ABOVE it. Anything
    below it is invisible to `python3 tests/test_x.py`."""

    def test_every_main_guard_is_the_last_statement_in_its_module(self):
        misplaced = []
        for path in discover_test_modules():
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for position, node in enumerate(tree.body):
                if not isinstance(node, ast.If):
                    continue
                if ast.unparse(node.test) != "__name__ == '__main__'":
                    continue
                if position != len(tree.body) - 1:
                    below = [
                        getattr(later, "name", type(later).__name__)
                        for later in tree.body[position + 1:]
                    ]
                    misplaced.append((path.name, below))

        self.assertEqual(misplaced, [])

    def test_every_test_module_carries_the_guard(self):
        """The guard is found in the syntax tree, not in the text. A module
        that only speaks about `__main__` in a docstring does not carry it."""
        self.assertEqual(
            [path.name for path in discover_test_modules() if not carries_guard(path)],
            [],
        )


class ReadmeFixtureTableTest(unittest.TestCase):
    """Every committed fixture has a row in the README table, and every row
    names a fixture that exists."""

    def documented(self):
        text = README.read_text(encoding="utf-8")
        found = set()
        for line in text.splitlines():
            if not line.startswith("|"):
                continue
            for cell in line.split("|"):
                for token in cell.replace("`", " ").replace(",", " ").split():
                    if token.endswith(".md") or token.endswith("/"):
                        found.add(token)
        return found

    def committed(self):
        names = {path.name for path in FIXTURES.glob("*.md")}
        names |= {f"{path.name}/" for path in FIXTURES.iterdir() if path.is_dir()}
        return names

    def test_every_fixture_has_a_row_in_the_readme_table(self):
        committed = self.committed()
        self.assertIn("clean_plan.md", committed)  # an empty scan makes the next line pass
        self.assertEqual(sorted(committed - self.documented()), [])

    def test_every_readme_row_names_a_fixture_that_exists(self):
        rows = {name for name in self.documented() if name.startswith(("neg_", "pos_", "clean_", "repo_"))}
        self.assertIn("clean_plan.md", rows)  # an empty table makes the next line pass
        self.assertEqual(sorted(rows - self.committed()), [])


class TestModuleDiscoveryTest(unittest.TestCase):
    """`discover_test_modules()` drives four assertions in this file. Each one
    examines a list that is built from that scan. An empty scan makes all four
    pass and verify nothing. Thus the scan itself is asserted here.

    This is the assertion that `test_modules()` never made. That function had a
    `test_` prefix, so `pytest` collected it, but it only returned a list.
    """

    def independent_scan(self):
        """The same set of names, found with `os.listdir` and not with `glob`."""
        return sorted(
            name
            for name in os.listdir(TESTS)
            if name.startswith("test_") and name.endswith(".py")
        )

    def test_discovery_finds_every_committed_test_module(self):
        self.assertEqual(
            [path.name for path in discover_test_modules()], self.independent_scan()
        )

    def test_discovery_is_not_empty(self):
        self.assertIn("test_suite_integrity.py", self.independent_scan())

    def test_every_discovered_module_holds_at_least_one_test(self):
        """A module that the scan reads but finds no test in is a module whose
        tests are silently absent from every assertion in this file."""
        empty = [
            path.name for path in discover_test_modules() if not qualified_names(path)
        ]

        self.assertEqual(empty, [])


class ReturnedValueTest(unittest.TestCase):
    """A test that returns a value in place of an assertion verifies nothing.

    `pytest` collects such a test, prints `PytestReturnNotNoneWarning`, and
    passes it. `unittest` does not collect a module-level one at all. Neither
    runner fails. This is the same defect class as a check that cannot fail,
    so it is asserted here mechanically.
    """

    def test_no_collected_test_returns_a_value(self):
        offenders = []
        for path in discover_test_modules():
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for _, function in collected_tests(tree):
                for node in returned_values(function):
                    offenders.append(f"{path.name}::{function.name}:{node.lineno}")

        self.assertEqual(offenders, [])

    def test_the_two_runners_collect_the_same_tests(self):
        """`pytest` also collects a module-level `test*` function. `unittest`
        does not. A count that differs between the runners means one runner
        holds a test that the other never runs."""
        scanned = sorted(
            name for path in discover_test_modules() for name in qualified_names(path)
        )

        self.assertEqual(scanned, sorted(loaded_names()))


if __name__ == "__main__":
    unittest.main()
