"""Tests for the citation lint — the repository half of section 24.6's form.

The union half is `planlint.markers`: it asks whether every declared path is
NAMED by some entry. This half asks the other question, and section 24.6 states
in its own words that the two are not one finding: whether the commit an entry
names ever touched the path that entry claims.

The check is one command per cited commit — `git show --format= --name-only
<sha>` in the repository the entry names — so this lint needs no build tree and
no network. It needs a CLONE, and where it has none it says so.

The repositories here are REAL and built by the test. A mock of `git show`
would assert that the mock behaves, and the two shapes this lint exists to
distinguish — a commit that touched a path and a commit that did not — are
exactly the two a mock cannot tell apart on its own authority.
"""

import pathlib
import shutil
import subprocess
import tempfile
import unittest
import unittest.mock

from planlint import citations
from planlint.document import PlanDocument

HAS_GIT = shutil.which("git") is not None


def git(root, *args):
    """One git command in `root`, with an identity the environment cannot move."""
    result = subprocess.run(
        [
            "git",
            "-C",
            str(root),
            "-c",
            "user.name=planlint test",
            "-c",
            "user.email=planlint@example.invalid",
            "-c",
            "commit.gpgsign=false",
            *args,
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def commit(root, paths, subject):
    """Write every path, commit them, and return the commit's full sha."""
    for path in paths:
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(subject, encoding="utf-8")
    git(root, "add", "-A")
    git(root, "commit", "-m", subject)
    return git(root, "rev-parse", "HEAD")


def build_repository(root):
    """A repository with two commits touching two disjoint sets of paths."""
    git(root, "init", "-q", "-b", "main")
    first = commit(root, ["src/one.cpp", "tests/t0_one.cpp"], "the first commit")
    second = commit(root, ["src/two.cpp"], "the second commit")
    return first, second


def plan(marker):
    return PlanDocument.from_text(
        "## 9. The tasks\n"
        "\n"
        "**AAA-1 · A task** — T0\n"
        "Files: `src/one.cpp`\n"
        "Depends: none\n"
        "Check: `ctest --test-dir build --no-tests=error -R t0_one`\n"
        f"{marker}\n",
        name="inline",
    )


def rows(result):
    return [(f.rule, f.task, f.severity, f.evidence) for f in result.findings]


@unittest.skipUnless(HAS_GIT, "git is not on PATH, so no clone can be read")
class CommitInPathHistoryTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name) / "core"
        self.root.mkdir()
        self.first, self.second = build_repository(self.root)
        self.clones = {"axiomantic/core": self.root}
        self.addCleanup(self.tmp.cleanup)

    def test_an_entry_whose_commit_touched_the_path_is_silent(self):
        doc = plan(
            "**DONE. CITED PER DECLARED PATH:** `axiomantic/core` "
            f"`{self.first}` → `src/one.cpp`, `tests/t0_one.cpp`."
        )

        self.assertEqual(citations.run(doc, clones=self.clones).findings, [])

    def test_an_entry_whose_commit_never_touched_the_path_is_reported(self):
        doc = plan(
            "**DONE. CITED PER DECLARED PATH:** `axiomantic/core` "
            f"`{self.second}` → `src/one.cpp`."
        )

        self.assertEqual(
            rows(citations.run(doc, clones=self.clones)),
            [
                (
                    "done-marker-commit-not-in-path-history",
                    "AAA-1",
                    "ERROR",
                    f"`axiomantic/core` `{self.second}` is cited for "
                    "`src/one.cpp`; `git show --format= --name-only "
                    f"{self.second}` in that clone lists 1 path and "
                    "`src/one.cpp` is not one of them",
                )
            ],
        )

    def test_the_message_states_what_the_repository_refutes(self):
        doc = plan(
            "**DONE. CITED PER DECLARED PATH:** `axiomantic/core` "
            f"`{self.second}` → `src/one.cpp`."
        )

        self.assertEqual(
            [f.message for f in citations.run(doc, clones=self.clones).findings],
            [
                "a completion marker's citation names a commit for a path that "
                "commit never touched. An entry states which commit covered "
                "which path, so an entry naming a path outside its own commit "
                "is a claim the repository refutes"
            ],
        )

    def test_an_abbreviated_sha_resolves_like_a_whole_one(self):
        doc = plan(
            "**DONE. CITED PER DECLARED PATH:** `axiomantic/core` "
            f"`{self.first[:7]}` → `src/one.cpp`."
        )

        self.assertEqual(citations.run(doc, clones=self.clones).findings, [])

    def test_a_glob_entry_is_covered_by_any_file_that_matches_it(self):
        """A citation may name a GLOB, because a `Files:` line may. CPU-7,
        CPU-8 and CPU-9 each declare a `conformance/corpus/*_*.json` corpus and
        cite it. `--name-only` prints the literal files, so comparing the two
        as strings refutes every corpus declaration in the plan. That is what
        the first run of this rule against the real document did."""
        doc = plan(
            "**DONE. CITED PER DECLARED PATH:** `axiomantic/core` "
            f"`{self.first}` → `src/*.cpp`."
        )

        self.assertEqual(citations.run(doc, clones=self.clones).findings, [])

    def test_a_glob_entry_that_matches_nothing_the_commit_touched_is_reported(self):
        """The other half. A glob that resolves to nothing is still a claim the
        repository refutes, and a rule that admitted every glob would decide
        nothing while printing the same clean line."""
        doc = plan(
            "**DONE. CITED PER DECLARED PATH:** `axiomantic/core` "
            f"`{self.first}` → `docs/*.md`."
        )

        self.assertEqual(
            [f.rule for f in citations.run(doc, clones=self.clones).findings],
            ["done-marker-commit-not-in-path-history"],
        )

    def test_a_directory_entry_is_covered_by_any_file_beneath_it(self):
        """A citation may name a DIRECTORY — REPO-14's names `planlint/` — and
        `--name-only` prints files. Comparing the two as strings would report a
        directory no commit can ever touch."""
        doc = plan(
            "**DONE. CITED PER DECLARED PATH:** `axiomantic/core` "
            f"`{self.first}` → `tests/`."
        )

        self.assertEqual(citations.run(doc, clones=self.clones).findings, [])


@unittest.skipUnless(HAS_GIT, "git is not on PATH, so no clone can be read")
class UndecidedTest(unittest.TestCase):
    """WHAT THIS LINT CANNOT DECIDE, asserted rather than described.

    Three states are not a verdict, and each is REPORTED. A scan that reads
    nothing and a scan that passes everything print the same result, so this
    lint refuses to print the second when it did the first.
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name) / "core"
        self.root.mkdir()
        self.first, self.second = build_repository(self.root)
        self.clones = {"axiomantic/core": self.root}
        self.addCleanup(self.tmp.cleanup)

    def test_a_repository_with_no_clone_is_undecided(self):
        doc = plan(
            "**DONE. CITED PER DECLARED PATH:** `axiomantic/elsewhere` "
            f"`{self.first}` → `src/one.cpp`."
        )

        self.assertEqual(
            rows(citations.run(doc, clones=self.clones)),
            [
                (
                    "done-marker-citation-undecided",
                    "AAA-1",
                    "WARNING",
                    f"`axiomantic/elsewhere` `{self.first}` cited for "
                    "`src/one.cpp`: no clone was supplied for that repository, "
                    "so nothing was read"
                )
            ],
        )

    def test_a_sha_the_clone_does_not_resolve_is_undecided(self):
        """A sha the clone cannot resolve is not a refutation. The clone may be
        behind, or on another remote; naming it a violation would report a
        finding about this machine and dress it as one about the document."""
        doc = plan(
            "**DONE. CITED PER DECLARED PATH:** `axiomantic/core` "
            "`0123456789abcdef0123456789abcdef01234567` → `src/one.cpp`."
        )

        self.assertEqual(
            rows(citations.run(doc, clones=self.clones)),
            [
                (
                    "done-marker-citation-undecided",
                    "AAA-1",
                    "WARNING",
                    "`axiomantic/core` "
                    "`0123456789abcdef0123456789abcdef01234567` cited for "
                    "`src/one.cpp`: the clone supplied for that repository does "
                    "not resolve the sha",
                )
            ],
        )

    def test_a_merge_commit_is_undecided_and_never_read_as_touching_nothing(self):
        """`git show --format= --name-only` prints NOTHING for a merge. Reading
        that as an empty path set would refute every path a merge is cited for,
        which is a false ERROR built out of a silence."""
        git(self.root, "checkout", "-q", "-b", "side", self.first)
        side = commit(self.root, ["src/side.cpp"], "the side commit")
        git(self.root, "checkout", "-q", "main")
        git(self.root, "merge", "--no-ff", "-m", "the merge", side)
        merge = git(self.root, "rev-parse", "HEAD")

        doc = plan(
            "**DONE. CITED PER DECLARED PATH:** `axiomantic/core` "
            f"`{merge}` → `src/one.cpp`."
        )

        self.assertEqual(
            rows(citations.run(doc, clones=self.clones)),
            [
                (
                    "done-marker-citation-undecided",
                    "AAA-1",
                    "WARNING",
                    f"`axiomantic/core` `{merge}` cited for `src/one.cpp`: the "
                    "sha is a MERGE commit, and `--name-only` prints no path "
                    "for one, so touching nothing and being a merge are "
                    "indistinguishable here",
                )
            ],
        )

    def test_git_missing_from_the_machine_is_undecided_and_never_a_crash(self):
        """The only mock in this file, and it stands for a condition the test
        cannot create: a machine with no `git`. A traceback out of one lint
        takes the whole report's verdict line with it, so the state that means
        "this machine cannot read a repository" has to arrive as a finding."""
        doc = plan(
            "**DONE. CITED PER DECLARED PATH:** `axiomantic/core` "
            f"`{self.first}` → `src/one.cpp`."
        )

        with unittest.mock.patch(
            "subprocess.run", side_effect=FileNotFoundError("git")
        ):
            result = citations.run(doc, clones=self.clones)

        self.assertEqual(
            rows(result),
            [
                (
                    "done-marker-citation-undecided",
                    "AAA-1",
                    "WARNING",
                    f"`axiomantic/core` `{self.first}` cited for `src/one.cpp`: "
                    "no `git` could be run on this machine, so no repository "
                    "was read",
                )
            ],
        )

    def test_a_run_with_no_clone_at_all_decides_nothing_and_says_so(self):
        doc = plan(
            "**DONE. CITED PER DECLARED PATH:** `axiomantic/core` "
            f"`{self.first}` → `src/one.cpp`."
        )

        self.assertEqual(
            [f.rule for f in citations.run(doc, clones={}).findings],
            ["done-marker-citation-undecided"],
        )


@unittest.skipUnless(HAS_GIT, "git is not on PATH, so no clone can be read")
class NoInputTest(unittest.TestCase):
    def test_a_document_with_no_task_block_is_a_hard_error(self):
        doc = PlanDocument.from_text("# A document with no task\n", name="inline")

        self.assertEqual(
            [
                (f.rule, f.message, f.severity)
                for f in citations.run(doc, clones={}).findings
            ],
            [("no-input", "the citation lint examined 0 task bodies", "ERROR")],
        )

    def test_a_plan_whose_markers_cite_no_entry_reports_a_pair_count_of_zero(self):
        """The DECIDED boundary of the guard, and it is a decision rather than
        an oversight. A plan whose markers predate the citation form has no
        pair for this lint to read — 88 of the plan's markers are in that state
        — and `planlint.markers` reports every one of them as
        `done-marker-citation-not-in-form`. A second alarm on the same fact
        would say nothing new and would drown the first. The COUNT still
        prints, so a run that read nothing says so beside its verdict."""
        result = citations.run(
            plan("**DONE on 2026-01-01, commit `1111111`.**"), clones={}
        )

        self.assertEqual(
            (result.findings, result.examined, result.examined_label),
            ([], 0, "cited (commit, path) pairs"),
        )


if __name__ == "__main__":
    unittest.main()
