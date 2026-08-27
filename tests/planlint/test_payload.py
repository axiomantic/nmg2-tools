"""Tests for the artifact-boundary lint (sections 3.2, 7.8, 22.4).

No Clavia-authored content reaches a public repository by ANY route: a commit, a
fixture path, a test vector, a `.gitmodules` entry, or a continuous-integration
step that uploads a build artifact. The last route is the one a lint that reads
committed files only cannot see at all.
"""

import pathlib
import subprocess
import tempfile
import unittest

from tests.planlint.support import fixture_path, load_fixture

from planlint import payload

PCH2_EVIDENCE = (
    "is outside `nmg2_tools/testdata/pch2_synth/`, the only directory in a "
    "public repository where a `*.pch2` file may live"
)


def run(tree, **kwargs):
    doc = load_fixture("clean_plan.md")
    kwargs.setdefault("register", doc.fixture_register)
    return payload.run(fixture_path(tree), **kwargs)


def git(root, *args):
    return subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True,
        text=True,
        check=True,
    ).stdout


def build_repo(root):
    """A real repository holding a known positive and a known negative.

    `patches/` gets two `*.pch2` files, identical in every respect the lint
    reads except one: one is in the index and the other is not. They sit in ONE
    directory so that no path rule, suffix rule or ceiling can be the reason
    the lint parts them. Only membership of the tracked population can be.
    """
    (root / "patches").mkdir(parents=True)
    (root / "patches" / "tracked.pch2").write_bytes(b"payload")
    git(root, "init", "-q")
    git(root, "add", "patches/tracked.pch2")
    git(
        root,
        "-c", "user.email=planlint@example.invalid",
        "-c", "user.name=planlint",
        "commit", "-q", "-m", "one",
    )
    (root / "patches" / "untracked.pch2").write_bytes(b"payload")
    return root


class PayloadLintTest(unittest.TestCase):
    def test_the_good_tree_reports_nothing(self):
        result = run("repo_public_good")

        self.assertEqual(result.findings, [])
        self.assertEqual(result.examined, 6)

    def test_every_breach_route_is_reported_and_nothing_else(self):
        result = run("repo_public_bad")

        self.assertEqual(
            sorted((f.rule, f.evidence) for f in result.findings),
            [
                (
                    "no-clavia-payload-oversize",
                    "`fixtures/over_ceiling.bin` is 65537 bytes, above the 65536-byte "
                    "ceiling, and section 7.8's register carries no allow-listed row "
                    "for it",
                ),
                (
                    "no-clavia-payload-pch2",
                    "`patches/demo_bank.pch2` is outside "
                    "`nmg2_tools/testdata/pch2_synth/`, the only directory in a public "
                    "repository where a `*.pch2` file may live",
                ),
                (
                    "no-clavia-upload",
                    "`.github/jobs/oracle.yml` step `actions/cache` carries path "
                    "`corpus/pch2`, which intersects a corpus",
                ),
                (
                    "no-clavia-upload",
                    "`.github/workflows/ci.yml` step `actions/upload-artifact` carries "
                    "path `build/golden/captures`, which intersects a capture",
                ),
                (
                    "no-private-submodule",
                    "`.gitmodules` names "
                    "`https://github.com/axiomantic/nmg2-artifacts.git`",
                ),
            ],
        )

    def test_a_file_exactly_at_the_ceiling_passes_and_one_byte_above_fails(self):
        result = run("repo_public_bad")
        oversize = [f for f in result.findings if f.rule == "no-clavia-payload-oversize"]

        self.assertEqual(
            [f.evidence for f in oversize],
            [
                "`fixtures/over_ceiling.bin` is 65537 bytes, above the 65536-byte "
                "ceiling, and section 7.8's register carries no allow-listed row for it"
            ],
        )
        self.assertEqual(payload.DEFAULT_CEILING, 65536)

    def test_an_allow_listed_register_row_exempts_a_file_above_the_ceiling(self):
        result = run("repo_public_bad")
        evidence = " ".join(f.evidence for f in result.findings)

        # The tree must still report something. An empty haystack makes the
        # assertion below pass while the lint examines nothing.
        self.assertIn("fixtures/over_ceiling.bin", evidence)
        self.assertNotIn("conformance/corpus/move_group.json", evidence)

    def test_without_the_allow_listed_row_the_same_file_is_reported(self):
        result = run("repo_public_bad", register=[])

        self.assertIn(
            "`conformance/corpus/move_group.json` is 65602 bytes, above the "
            "65536-byte ceiling, and section 7.8's register carries no allow-listed "
            "row for it",
            [f.evidence for f in result.findings],
        )

    def test_a_private_repository_is_where_the_payload_belongs(self):
        result = run("repo_public_bad", public=False)

        self.assertEqual(result.findings, [])

    def test_an_empty_tree_is_a_hard_error(self):
        result = payload.run(fixture_path("repo_public_good") / "no_such_dir")

        self.assertEqual(
            [(f.rule, f.message) for f in result.findings],
            [("no-input", "the payload lint examined 0 tracked files")],
        )
        self.assertEqual(result.examined, 0)


class TrackedPopulationTest(unittest.TestCase):
    """The population the lint reads is the one its report NAMES.

    It read every file on disk — a `.venv`, a `.pytest_cache`, any untracked
    scratch file — and called the result "committed files". A reader cannot
    tell that report from one taken over the repository, which is the whole
    value the line claims to carry.
    """

    def test_a_tracked_file_is_reported_and_its_untracked_sibling_is_not(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = payload.run(build_repo(pathlib.Path(tmp)), register=[])

        self.assertEqual(
            [(f.rule, f.evidence) for f in result.findings],
            [("no-clavia-payload-pch2", f"`patches/tracked.pch2` {PCH2_EVIDENCE}")],
        )
        self.assertEqual(result.examined, 1)
        self.assertEqual(result.examined_label, "tracked files")

    def test_the_walk_returns_exactly_the_tracked_files_of_the_tree(self):
        tree = fixture_path("repo_public_bad")

        self.assertEqual(
            [str(path.relative_to(tree)) for path in payload._walk(tree)],
            [
                ".github/jobs/oracle.yml",
                ".github/workflows/ci.yml",
                ".gitmodules",
                "README.md",
                "conformance/corpus/move_group.json",
                "fixtures/at_ceiling.bin",
                "fixtures/over_ceiling.bin",
                "nmg2_tools/testdata/pch2_synth/synth_min.pch2",
                "patches/demo_bank.pch2",
            ],
        )

    def test_a_repository_with_no_tracked_file_is_a_hard_error(self):
        """The trap. `ctest -R` exits 0 when its pattern matches no test, so
        this tool never exits 0 on "nothing to check". Narrowing the population
        to the index must not turn an unindexed tree into a clean report."""
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            git(root, "init", "-q")
            (root / "patches").mkdir()
            (root / "patches" / "leak.pch2").write_bytes(b"payload")
            result = payload.run(root)

        self.assertEqual(
            [(f.rule, f.message) for f in result.findings],
            [("no-input", "the payload lint examined 0 tracked files")],
        )
        self.assertEqual(result.examined, 0)
        self.assertTrue(result.failed)

    def test_a_directory_that_is_no_repository_is_a_hard_error(self):
        """A tree git cannot answer for fails CLOSED. Reading the disk instead
        would be the defect this change removes, arriving through a fallback."""
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / "patches").mkdir()
            (root / "patches" / "leak.pch2").write_bytes(b"payload")
            result = payload.run(root)

        self.assertEqual(
            [(f.rule, f.message) for f in result.findings],
            [("no-input", "the payload lint examined 0 tracked files")],
        )
        self.assertEqual(result.examined, 0)
        self.assertTrue(result.failed)

    def test_a_private_repository_counts_the_same_population(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = payload.run(build_repo(pathlib.Path(tmp)), public=False)

        self.assertEqual(result.findings, [])
        self.assertEqual(result.examined, 1)
        self.assertEqual(result.examined_label, "tracked files")


if __name__ == "__main__":
    unittest.main()
