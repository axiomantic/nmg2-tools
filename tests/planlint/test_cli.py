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
from unittest import mock

from tests.planlint.support import fixture_path

from planlint import cli, finding
from planlint.finding import WARNING, Finding, LintResult

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
            "RESULT: SELECTED LINTS CLEAN. 4 lints SKIPPED (citations, "
            "payload, provenance, registries). A skipped lint is not a "
            "clean lint.",
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

    The quoted string is a RECORD of what was observed then, and it is left as
    written: the lint has since been repaired to read `git ls-files` and now
    prints "tracked files examined", so this exact line can no longer be
    produced. That is the point of keeping it -- the wording it quotes is the
    wording that made the two runs indistinguishable.
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
            "RESULT: SELECTED LINTS CLEAN. 4 lints SKIPPED (citations, "
            "payload, provenance, registries). A skipped lint is not a "
            "clean lint.",
        )

    def test_a_run_with_findings_and_a_skip_states_both(self):
        code, text = run(["--plan", str(fixture_path("neg_graph_cycle.md"))])

        self.assertEqual(code, 1)
        self.assertEqual(
            result_line(text),
            "RESULT: findings reported. See each rule above. "
            "4 lints SKIPPED (citations, payload, provenance, registries). A skipped lint "
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
                "--source-repo", "core=" + str(fixture_path("repo_registry_good")),
            ]
        )

        self.assertEqual(code, 0)
        self.assertEqual(section_names(text), cli.ALL_LINTS)
        self.assertEqual(
            section_line(text, "payload"), "payload: clean (6 tracked files examined)"
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
                "registries",
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
                "registries": 20,
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


class WarningCollapseTest(unittest.TestCase):
    """The default report collapses every severity below ERROR to one line per
    rule, and `--full-warnings` prints the lines it collapsed.

    The measured reason for the collapse, and the reason it goes this
    direction only: one run over the plan reported 121 ERROR and 667 WARNING,
    three warning rules produced 573 of the 667, and two ERRORs naming a check
    that could not fail sat unread in the tail for months. Collapsing is a
    change to the REPORT. No rule is re-scoped, nothing is dropped from
    `findings`, and the exit code is what it always was.
    """

    # A finding line printed in full sits at two spaces. A collapsed summary
    # line sits at four and carries a count. The two indents make the patterns
    # non-overlapping, so a line counted by one is never seen by the other.
    FULL_LINE = re.compile(r"^  \[WARNING\] (?P<rule>\S+)")
    SUMMARY_LINE = re.compile(r"^    \[WARNING\] (?P<rule>\S+)  (?P<count>\d+)$")

    # A fixture whose warnings are more than one rule and more than one finding
    # per rule: 6 of one and 3 of the other. A fixture with one warning would
    # let a summary that printed the finding itself pass as a collapse.
    FIXTURE = "neg_gate_dispositions.md"

    def full_report_counts(self, text):
        """{rule: printed finding lines}, read off a FULL report.

        Derived by COUNTING lines. Nothing here reads a stated number, so this
        side cannot inherit an error from the summary it is compared against.
        """
        counts = {}
        for line in text.splitlines():
            match = self.FULL_LINE.match(line)
            if match:
                counts[match.group("rule")] = counts.get(match.group("rule"), 0) + 1
        return counts

    def summary_counts(self, text):
        """{rule: the number the summary STATES}, read off a COLLAPSED report.

        Derived by PARSING a stated number. Nothing here counts findings, so
        this side cannot inherit a count from the full report.
        """
        counts = {}
        for line in text.splitlines():
            match = self.SUMMARY_LINE.match(line)
            if match:
                counts[match.group("rule")] = int(match.group("count"))
        return counts

    def assert_collapse_is_lossless(self, fixture):
        """The two sides agree, each derived from its OWN rendering.

        This is the assertion the planted-undercount test below turns red, and
        it is reached through this one method so that the planted case and the
        live case cannot drift apart.
        """
        plan = str(fixture_path(fixture))
        _, collapsed = run(["--plan", plan])
        _, full = run(["--plan", plan, "--full-warnings"])

        stated = self.summary_counts(collapsed)
        printed = self.full_report_counts(full)

        self.assertTrue(printed, "the fixture reported no warning at all")
        self.assertEqual(stated, printed)

    def test_the_collapse_states_the_number_of_lines_the_full_report_prints(self):
        self.assert_collapse_is_lossless(self.FIXTURE)

    def test_the_collapse_is_lossless_on_a_single_rule_with_many_findings(self):
        self.assert_collapse_is_lossless("neg_removed_exclusions.md")

    def test_a_summary_that_under_counts_one_rule_turns_the_losslessness_red(self):
        """The planted failure.

        Without this, a green losslessness test proves only that the run was
        quiet. One finding is removed from what the summary counts — the
        smallest possible under-count, and the shape a collapse actually fails
        in — and the assertion above must reach a caller as a failure.
        """
        honest = LintResult.collapsed_counts

        def under_counting(result):
            rows = honest(result)
            return [
                (severity, rule, count - 1 if index == 0 else count)
                for index, (severity, rule, count) in enumerate(rows)
            ]

        with mock.patch.object(
            LintResult, "collapsed_counts", under_counting
        ), self.assertRaises(AssertionError):
            self.assert_collapse_is_lossless(self.FIXTURE)

    def test_the_planted_under_count_is_the_only_thing_that_changed(self):
        """The control for the test above: with the patch lifted, the same
        call passes. A planted failure that left the fixture broken would turn
        the assertion red for a reason that is not the plant."""
        self.assert_collapse_is_lossless(self.FIXTURE)

    def test_the_collapsed_report_names_the_flag_that_prints_the_rest(self):
        """A reader who cannot see how to expand is looking at suppression
        whatever the code calls it. The flag is named in the lint's own block
        AND once for the run."""
        _, text = run(["--plan", str(fixture_path(self.FIXTURE))])

        self.assertIn(
            "collapsed to one line per rule; --full-warnings prints every one:",
            text,
        )
        self.assertIn(
            "NOTE: 9 findings below ERROR collapsed to 2 rules. Nothing was "
            "suppressed: --full-warnings prints every one.",
            text,
        )

    def test_the_flag_the_report_names_is_a_flag_the_parser_accepts(self):
        """The sentence a reader acts on and the argument the parser registers
        are the SAME constant. A report naming a flag the parser rejects would
        be suppression that reads as recovery."""
        actions = {
            option
            for action in cli.build_parser()._actions
            for option in action.option_strings
        }

        self.assertIn(finding.RECOVERY_FLAG, actions)
        self.assertIn(finding.RECOVERY_FLAG, "--full-warnings")

    def test_every_error_is_printed_in_full_in_both_modes(self):
        """The collapse goes one direction only. The ERRORs are the findings
        the noise was hiding, so a mode that collapsed them would undo the
        whole change."""
        plan = str(fixture_path(self.FIXTURE))
        _, collapsed = run(["--plan", plan])
        _, full = run(["--plan", plan, "--full-warnings"])

        def errors(text):
            return [
                line
                for line in text.splitlines()
                if line.startswith("  [ERROR] ")
            ]

        self.assertTrue(errors(collapsed))
        self.assertEqual(errors(collapsed), errors(full))

    def test_the_head_line_states_the_whole_count_in_both_modes(self):
        """The per-lint head says how many findings the lint reported, not how
        many lines the report chose to print. A head that counted printed
        lines would make the collapse read as a smaller result."""
        plan = str(fixture_path(self.FIXTURE))
        _, collapsed = run(["--plan", plan])
        _, full = run(["--plan", plan, "--full-warnings"])

        self.assertEqual(section_line(collapsed, "gate"), section_line(full, "gate"))
        self.assertIn("finding(s)", section_line(collapsed, "gate"))


class CollapseExitCodeTest(unittest.TestCase):
    """The collapse changes the report's WORDING and never its exit code.

    `cli`'s own docstring reasons this way about a SKIPPED lint: scoring it
    would change what `if planlint; then` means for every existing caller,
    which is a separate decision from making the skip visible. The same
    reasoning binds here.
    """

    def assert_same_code(self, argv, expected):
        collapsed, _ = run(argv)
        full, _ = run([*argv, "--full-warnings"])

        self.assertEqual(collapsed, expected)
        self.assertEqual(full, expected)

    def test_a_clean_plan_exits_zero_in_both_modes(self):
        self.assert_same_code(["--plan", str(fixture_path("clean_plan.md"))], 0)

    def test_a_plan_with_errors_and_warnings_exits_one_in_both_modes(self):
        self.assert_same_code(
            ["--plan", str(fixture_path("neg_gate_dispositions.md"))], 1
        )

    def test_a_warning_alone_still_exits_one_in_both_modes(self):
        """A collapsed rule line is still a finding. A run whose only findings
        were collapsed must not read as clean."""
        result = LintResult(
            name="checks",
            findings=[Finding(rule="r", message="m", severity=WARNING)],
            examined=1,
        )

        self.assertTrue(result.failed)
        self.assertIn("[WARNING] r  1", result.report(full=False))

    def test_an_invocation_error_exits_two_in_both_modes(self):
        self.assert_same_code(["--plan", "/no/such/plan.md"], 2)

    def test_the_skipped_notice_survives_the_collapse(self):
        """Four lints skip without `--repo`/`--clone`/`--source-repo`, and
        the verdict names
        them because a skipped lint is not a clean lint. The collapse notice
        is a SEPARATE line and never edits the verdict."""
        plan = str(fixture_path("clean_plan.md"))
        expected = (
            "RESULT: SELECTED LINTS CLEAN. 4 lints SKIPPED (citations, "
            "payload, provenance, registries). A skipped lint is not a "
            "clean lint."
        )
        for argv in ([], ["--full-warnings"]):
            _, text = run(["--plan", plan, *argv])

            self.assertEqual(result_line(text), expected)
            self.assertIn("citations: SKIPPED — no --clone given", text)

    def test_a_run_with_nothing_to_collapse_prints_no_collapse_notice(self):
        """The notice reports a collapse that happened. Printing it over a
        clean run would make it furniture a reader learns to skip."""
        _, text = run(["--plan", str(fixture_path("clean_plan.md"))])

        self.assertNotIn("NOTE:", text)


if __name__ == "__main__":
    unittest.main()

