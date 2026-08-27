"""Tests for the command line and its exit codes.

Exit 0 is clean. Any finding exits non-zero. A lint that found no input to
examine exits non-zero too: nothing to check is never a pass.
"""

import argparse
import ast
import io
import pathlib
import re
import tempfile
import unittest

from tests.planlint.support import fixture_path

from planlint import cli

PACKAGE = pathlib.Path(cli.__file__).resolve().parent

SECTION = re.compile(r"^(?P<name>[a-z0-9]+): (?P<rest>.*)$")
ORDINAL = re.compile(r"^Lint (?P<number>\d+) — ")


def run(argv):
    out = io.StringIO()
    code = cli.main(argv, stream=out)
    return code, out.getvalue()


def section_names(text):
    """The lint each section line names, in report order."""
    out = []
    for line in text.splitlines():
        match = SECTION.match(line)
        if match and match.group("name") != "planlint":
            out.append(match.group("name"))
    return out


def section_line(text, name):
    """The one section line for `name`, or "" when the report has none."""
    for line in text.splitlines():
        match = SECTION.match(line)
        if match and match.group("name") == name:
            return line
    return ""


def result_line(text):
    for line in text.splitlines():
        if line.startswith("RESULT:"):
            return line
    return ""


class ExitCodeTest(unittest.TestCase):
    def test_a_clean_plan_exits_zero(self):
        """This invocation gives neither `--repo` nor `--clone`, so the payload
        lint and the citations lint do not run. The verdict says CLEAN of the
        lints that ran and names the two that did not; `ALL LINTS CLEAN` here
        would be a claim about lints this run never exercised."""
        code, text = run(["--plan", str(fixture_path("clean_plan.md"))])

        self.assertEqual(code, 0)
        self.assertIn("graph: clean", text)
        self.assertEqual(
            result_line(text),
            "RESULT: SELECTED LINTS CLEAN. 3 lints SKIPPED (citations, "
            "payload, provenance). A skipped lint is not a clean lint.",
        )

    def test_the_anchors_lint_runs_in_the_default_set_and_states_its_count(self):
        code, text = run(["--plan", str(fixture_path("clean_plan.md"))])

        self.assertEqual(code, 0)
        self.assertIn("anchors: clean (1 anchored figures examined)", text)

    def test_a_stale_anchored_figure_exits_non_zero_and_names_the_rule(self):
        """The whole path, end to end: a written figure that disagrees with the
        derivation reaches the exit code and the report line a caller acts on."""
        code, text = run(
            ["--plan", str(fixture_path("neg_anchors.md")), "--only", "anchors"]
        )

        self.assertEqual(code, 1)
        self.assertIn("[ERROR] derived-figure-stale", text)
        self.assertIn("RESULT: findings reported. See each rule above.", text)

    def test_a_plan_with_a_cycle_exits_non_zero(self):
        code, text = run(["--plan", str(fixture_path("neg_graph_cycle.md"))])

        self.assertEqual(code, 1)
        self.assertIn("dependency-cycle", text)

    def test_a_lint_with_no_input_exits_non_zero(self):
        code, text = run(["--plan", str(fixture_path("neg_graph_cycle.md")), "--only", "counts"])

        self.assertEqual(code, 1)
        self.assertIn("no-input", text)

    def test_only_selects_one_lint(self):
        code, text = run(["--plan", str(fixture_path("clean_plan.md")), "--only", "graph"])

        self.assertEqual(code, 0)
        self.assertIn("graph: clean", text)
        self.assertNotIn("waves:", text)

    def test_an_unknown_lint_name_exits_non_zero_and_names_the_choices(self):
        code, text = run(["--plan", str(fixture_path("clean_plan.md")), "--only", "ghost"])

        self.assertEqual(code, 2)
        self.assertIn("unknown lint 'ghost'", text)
        self.assertIn("graph", text)

    def test_the_repository_lint_runs_against_a_tree(self):
        code, text = run(
            [
                "--plan", str(fixture_path("clean_plan.md")),
                "--repo", str(fixture_path("repo_public_bad")),
                "--only", "payload",
            ]
        )

        self.assertEqual(code, 1)
        self.assertIn("no-clavia-upload", text)

    def test_payload_without_a_repository_argument_exits_non_zero(self):
        code, text = run(
            ["--plan", str(fixture_path("clean_plan.md")), "--only", "payload"]
        )

        self.assertEqual(code, 2)
        self.assertIn("--repo is required", text)

    def test_citations_without_a_clone_argument_exits_non_zero(self):
        """Naming a lint explicitly with its requirement unmet stays an ERROR
        and never becomes a skip: `--only` is the caller asking for that lint,
        and answering with a skip would tell them their request was honoured."""
        code, text = run(
            ["--plan", str(fixture_path("clean_plan.md")), "--only", "citations"]
        )

        self.assertEqual(code, 2)
        self.assertIn("--clone is required", text)

    def test_a_clone_argument_without_a_repository_name_exits_non_zero(self):
        code, text = run(
            [
                "--plan", str(fixture_path("clean_plan.md")),
                "--clone", str(fixture_path("repo_public_good")),
            ]
        )

        self.assertEqual(code, 2)
        self.assertIn("expected OWNER/REPO=PATH", text)

    def test_a_clone_path_that_is_not_a_directory_exits_non_zero(self):
        code, text = run(
            [
                "--plan", str(fixture_path("clean_plan.md")),
                "--clone", "axiomantic/core=/nonexistent/path/to/clone",
            ]
        )

        self.assertEqual(code, 2)
        self.assertIn("no such repository clone", text)

    def test_the_citation_lint_names_the_clone_flag_when_it_did_not_run(self):
        code, text = run(["--plan", str(fixture_path("clean_plan.md"))])

        self.assertEqual(
            section_line(text, "citations"),
            "citations: SKIPPED — no --clone given; the lint did not run and "
            "its result is unknown",
        )

    def test_a_run_with_a_clone_reports_the_pair_count_it_examined(self):
        """The coverage figure prints beside the verdict. A run that decided
        nothing and a run that decided a hundred pairs must not print the same
        line."""
        code, text = run(
            [
                "--plan", str(fixture_path("clean_plan.md")),
                "--clone", "axiomantic/core=" + str(fixture_path("repo_public_good")),
            ]
        )

        self.assertEqual(
            section_line(text, "citations"),
            "citations: clean (0 cited (commit, path) pairs examined)",
        )

    def test_a_missing_plan_file_exits_non_zero(self):
        code, text = run(["--plan", str(fixture_path("no_such_plan.md"))])

        self.assertEqual(code, 2)
        self.assertIn("no such plan document", text)

    def test_check_targets_option_runs_check_targets_validation(self):
        code, text = run(
            [
                "--plan", str(fixture_path("clean_plan.md")),
                "--check-targets", str(fixture_path("clean_check_targets.txt")),
            ]
        )

        self.assertEqual(code, 0)
        self.assertIn("checks: clean", text)

    def test_build_dir_option_with_invalid_path_exits_non_zero(self):
        code, text = run(
            [
                "--plan", str(fixture_path("clean_plan.md")),
                "--only", "checks",
                "--build-dir", "axiomantic/nord-g2=/nonexistent/path",
            ]
        )

        self.assertEqual(code, 1)
        self.assertIn("invalid-build-dir", text)

    def test_build_dir_option_with_valid_path_and_ctestfile_exits_zero(self):
        import pathlib
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            p = pathlib.Path(tmp)
            (p / "CTestTestfile.cmake").write_text(
                'add_test(t0_alpha "echo" "1")\n'
                'add_test(t0_beta "echo" "1")\n'
                'add_test(t1_gamma "echo" "1")\n'
                'add_test(t0_delta "echo" "1")\n'
                'add_test(t0_epsilon "echo" "1")\n'
                'add_test(t2_zeta "echo" "1")\n'
                'add_test(t0_eta "echo" "1")\n'
            )
            code, text = run(
                [
                    "--plan", str(fixture_path("clean_plan.md")),
                    "--only", "checks",
                    "--build-dir", f"axiomantic/nord-g2={tmp}",
                ]
            )

            self.assertEqual(code, 0)
            self.assertIn("checks: clean", text)


class SkippedLintVisibilityTest(unittest.TestCase):
    """A lint that did not run must say so.

    Measured against the plan at `nmg2-artifacts`: `--plan P` reported 41 ERROR
    findings and never named the payload lint; `--plan P --repo R --private`
    reported the same 41 and `payload: clean (3064 committed files examined)`.
    The run that never exercised the lint and the run in which it passed over
    3,064 files printed the same count and the same verdict. Every pass on this
    project took the first number as its baseline without knowing which of the
    two it held.
    """

    def test_a_default_run_with_no_repo_enumerates_every_lint(self):
        """The report is a roll call, not a list of what happened to run. A lint
        missing from it is a lint whose result the reader cannot infer."""
        code, text = run(["--plan", str(fixture_path("clean_plan.md"))])

        self.assertEqual(code, 0)
        self.assertEqual(section_names(text), cli.ALL_LINTS)

    def test_a_lint_that_did_not_run_names_itself_and_the_missing_flag(self):
        code, text = run(["--plan", str(fixture_path("clean_plan.md"))])

        self.assertEqual(
            section_line(text, "payload"),
            "payload: SKIPPED — no --repo given; the lint did not run and its "
            "result is unknown",
        )

    def test_the_verdict_does_not_claim_all_lints_clean_when_one_was_skipped(self):
        code, text = run(["--plan", str(fixture_path("clean_plan.md"))])

        self.assertEqual(code, 0)
        self.assertEqual(
            result_line(text),
            "RESULT: SELECTED LINTS CLEAN. 3 lints SKIPPED (citations, "
            "payload, provenance). A skipped lint is not a clean lint.",
        )

    def test_a_run_with_findings_and_a_skip_states_both(self):
        code, text = run(["--plan", str(fixture_path("neg_graph_cycle.md"))])

        self.assertEqual(code, 1)
        self.assertEqual(
            result_line(text),
            "RESULT: findings reported. See each rule above. "
            "3 lints SKIPPED (citations, payload, provenance). A skipped lint "
            "is not a clean lint.",
        )

    def test_a_run_in_which_every_lint_ran_says_nothing_about_a_skip(self):
        """The negative input. A notice that fires when nothing was skipped
        trains a reader to skim past the one that matters."""
        code, text = run(
            [
                "--plan", str(fixture_path("clean_plan.md")),
                "--repo", str(fixture_path("repo_public_good")),
                "--clone", "axiomantic/core=" + str(fixture_path("repo_public_good")),
            ]
        )

        self.assertEqual(code, 0)
        self.assertEqual(section_names(text), cli.ALL_LINTS)
        self.assertEqual(
            section_line(text, "payload"), "payload: clean (6 committed files examined)"
        )
        self.assertNotIn("SKIPPED", text)
        self.assertEqual(result_line(text), "RESULT: ALL LINTS CLEAN")

    def test_a_narrowed_run_reports_only_what_it_named(self):
        """`--only` is the caller's own record of what they asked for, so the
        lints it leaves out are not a silent narrowing and get no notice."""
        code, text = run(
            ["--plan", str(fixture_path("clean_plan.md")), "--only", "graph"]
        )

        self.assertEqual(code, 0)
        self.assertEqual(section_names(text), ["graph"])
        self.assertNotIn("SKIPPED", text)
        self.assertEqual(result_line(text), "RESULT: ALL LINTS CLEAN")

    def test_a_skip_does_not_move_the_exit_code(self):
        """The skip is announced, never scored. Making it a finding would change
        what a caller's `if planlint; then` means, and that is a separate
        decision from making the skip visible."""
        skipped = run(["--plan", str(fixture_path("clean_plan.md"))])[0]
        ran = run(
            [
                "--plan", str(fixture_path("clean_plan.md")),
                "--repo", str(fixture_path("repo_public_good")),
            ]
        )[0]

        self.assertEqual((skipped, ran), (0, 0))


class LintRegistryTest(unittest.TestCase):
    """The same trap, one level up: a future optional lint that nobody registers.

    The reason a lint did not run is a byproduct of the decision not to run it,
    so no second list can fall out of step with the first. What remains is a
    lint that leaves the default run through neither route, and that is what
    `validate_lint_registry` refuses.
    """

    def test_the_shipped_registry_accounts_for_every_lint(self):
        cli.validate_lint_registry()

    def test_a_lint_module_on_disk_that_no_table_names_raises(self):
        """The planted failure. A lint module is WRITTEN into the package and
        registered in neither table, which is the one route by which a lint can
        skip in silence: a population read out of `DOCUMENT_LINTS` cannot hold a
        name `DOCUMENT_LINTS` never got."""
        planted = PACKAGE / "_planted_lint.py"
        planted.write_text(
            '"""A lint module nobody registered."""\n'
            "\n"
            "from planlint.finding import LintResult\n"
            "\n"
            "\n"
            "def run(doc):\n"
            '    return LintResult(name="_planted_lint", findings=[], examined=1)\n',
            encoding="utf-8",
        )
        self.addCleanup(planted.unlink)

        with self.assertRaises(cli.LintRegistryError) as caught:
            cli.validate_lint_registry()

        self.assertEqual(
            str(caught.exception),
            "lint '_planted_lint' neither runs unconditionally nor declares what "
            "it requires, so a run that omits it could not name the reason",
        )

    def test_the_scan_names_every_lint_module_and_no_support_module(self):
        """Exact equality. `cli`, `document` and `finding` are support modules
        and expose no `run`; `graph` is both a helper and a lint and is IN."""
        self.assertEqual(
            cli.discover_lint_modules(),
            [
                "anchors",
                "checks",
                "citations",
                "closure",
                "counts",
                "gate",
                "graph",
                "implicit",
                "markers",
                "payload",
                "provenance",
                "registrar",
                "removed",
                "rule9",
                "secondwrite",
                "selfcite",
                "structure",
                "tiers",
                "waves",
            ],
        )

    def test_a_scan_that_finds_no_lint_module_raises(self):
        """The guard's own silent-failure mode. A scan that reads the wrong
        directory returns nothing, every registered lint is then vacuously
        accounted for, and the guard passes by finding nothing to check."""
        empty = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(empty.rmdir)

        with self.assertRaises(cli.LintRegistryError) as caught:
            cli.discover_lint_modules(empty)

        self.assertEqual(
            str(caught.exception),
            f"no lint module found in {empty}, so the registry would be checked "
            "against nothing and would pass by examining no lint",
        )

    def test_a_lint_that_neither_always_runs_nor_declares_a_requirement_raises(self):
        with self.assertRaises(cli.LintRegistryError) as caught:
            cli.validate_lint_registry(
                all_lints=["graph", "ghost"],
                always_run=("graph",),
                requirements={},
            )

        self.assertEqual(
            str(caught.exception),
            "lint 'ghost' neither runs unconditionally nor declares what it "
            "requires, so a run that omits it could not name the reason",
        )

    def test_a_requirement_for_a_lint_that_does_not_exist_raises(self):
        with self.assertRaises(cli.LintRegistryError) as caught:
            cli.validate_lint_registry(
                all_lints=["graph"],
                always_run=("graph",),
                requirements={"ghost": cli.Requirement("--ghost", lambda args: True)},
            )

        self.assertEqual(
            str(caught.exception),
            "a requirement is registered for 'ghost', which is not a lint",
        )

    def test_a_lint_in_both_tables_raises(self):
        """The requirement would decide nothing. A lint listed as always-running
        satisfies the first check through that branch, so deleting its
        requirement would move it into the default run in silence — the very
        silent narrowing this registry exists to make impossible."""
        with self.assertRaises(cli.LintRegistryError) as caught:
            cli.validate_lint_registry(
                all_lints=["graph"],
                always_run=("graph",),
                requirements={"graph": cli.Requirement("--tree", lambda args: True)},
            )

        self.assertEqual(
            str(caught.exception),
            "lint 'graph' both runs unconditionally and declares a requirement, "
            "so the requirement decides nothing and could be removed without "
            "any run changing",
        )

    def test_a_future_optional_lint_gets_its_skip_line_from_what_it_declares(self):
        """Nothing in the reporting code knows this lint's name or its flag."""
        selected, skipped = cli.default_selection(
            argparse.Namespace(ghost=None),
            all_lints=["graph", "ghost"],
            requirements={
                "ghost": cli.Requirement("--ghost-tree", lambda args: bool(args.ghost))
            },
        )

        self.assertEqual(selected, ["graph"])
        self.assertEqual(skipped, {"ghost": "no --ghost-tree given"})

    def test_a_satisfied_requirement_selects_the_lint_and_skips_nothing(self):
        selected, skipped = cli.default_selection(
            argparse.Namespace(ghost="/somewhere"),
            all_lints=["graph", "ghost"],
            requirements={
                "ghost": cli.Requirement("--ghost-tree", lambda args: bool(args.ghost))
            },
        )

        self.assertEqual(selected, ["graph", "ghost"])
        self.assertEqual(skipped, {})


class LintOrdinalTest(unittest.TestCase):
    """Each lint module opens `Lint N — `. Nothing in the tool read that number,
    so two modules could claim one ordinal and did. The number stays because
    `planlint/README.md` refers to lints by it; it is asserted here so that it
    is a checked fact rather than a hand-maintained one.
    """

    def ordinals(self):
        """The ordinal each lint module's docstring claims, read out of the
        source rather than recalled."""
        found = {}
        for name in cli.discover_lint_modules():
            path = PACKAGE / f"{name}.py"
            docstring = ast.get_docstring(
                ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            )
            match = ORDINAL.match(docstring or "")
            found[name] = int(match.group("number")) if match else None
        return found

    def test_every_lint_module_claims_the_ordinal_it_is_known_by(self):
        self.assertEqual(
            self.ordinals(),
            {
                "graph": 1,
                "waves": 2,
                "tiers": 3,
                "checks": 4,
                "payload": 5,
                "provenance": 18,
                "counts": 6,
                "implicit": 7,
                "registrar": 8,
                "closure": 9,
                "structure": 10,
                "anchors": 11,
                "markers": 12,
                "citations": 13,
                "secondwrite": 14,
                "removed": 15,
                "rule9": 16,
                "gate": 17,
                "selfcite": 19,
            },
        )

    def test_the_ordinals_are_a_numbering_and_not_a_set_of_labels(self):
        """One ordinal per lint, and no gap. A duplicate makes a reference to
        `lint N` ambiguous, which is the defect this test closes; a gap means a
        lint was dropped and its number left behind."""
        claimed = self.ordinals()

        self.assertEqual(
            sorted(claimed.values()),
            list(range(1, len(cli.discover_lint_modules()) + 1)),
        )


if __name__ == "__main__":
    unittest.main()

