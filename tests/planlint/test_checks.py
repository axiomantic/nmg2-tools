"""Tests for the check-command lint (sections 1.3 rules 9 and 10, 7.7, 7.4.2)."""

import unittest

from tests.planlint.support import load_fixture

from planlint import checks
from planlint.document import PlanDocument
from planlint.finding import ERROR


def run(name):
    return checks.run(load_fixture(name))


def pairs(result):
    return sorted((f.rule, f.task, f.evidence) for f in result.findings)


class AnchoredRArgumentTest(unittest.TestCase):
    """Section 7.7: a non-allow-listed `-R` argument is anchored `^…$`.

    The anchors are what stop a task's gate sweeping tests outside its own
    closure: an unanchored argument is a prefix and matches every registered
    name that carries it. The lint must read an anchored argument as naming the
    test between the anchors, or every anchored check in the plan reports
    `r-name-not-created` against a name that exists.
    """

    def test_an_anchor_pair_is_stripped(self):
        self.assertEqual(
            checks.r_arguments("ctest --test-dir build --no-tests=error -R ^t0_alpha$"),
            ["t0_alpha"],
        )

    def test_an_unanchored_argument_is_unchanged(self):
        self.assertEqual(
            checks.r_arguments("ctest --test-dir build --no-tests=error -R t1_"),
            ["t1_"],
        )

    def test_a_half_anchor_is_not_stripped(self):
        """`^t0_alpha` is still a prefix. It must keep failing the pool lookup
        rather than being quietly accepted as an anchored name."""
        self.assertEqual(
            checks.r_arguments("ctest --test-dir build --no-tests=error -R ^t0_alpha"),
            ["^t0_alpha"],
        )
        self.assertEqual(
            checks.r_arguments("ctest --test-dir build --no-tests=error -R t0_alpha$"),
            ["t0_alpha$"],
        )

    def test_an_anchored_name_no_files_line_creates_is_still_reported(self):
        """Stripping the anchors must not weaken the rule the anchors decorate."""
        self.assertEqual(
            checks.r_arguments("ctest --test-dir build --no-tests=error -R ^t0_absent$"),
            ["t0_absent"],
        )

    def test_a_shell_quoted_anchor_pair_is_stripped(self):
        """`$` is a shell metacharacter, so quoting an anchored argument is the
        natural way to write it. An unquoted read gives the name `'^t0_alpha`
        and a false `r-name-not-created` against a test that exists."""
        self.assertEqual(
            checks.r_arguments("ctest --no-tests=error -R '^t0_alpha$'"), ["t0_alpha"]
        )
        self.assertEqual(
            checks.r_arguments('ctest --no-tests=error -R "^t0_alpha$"'), ["t0_alpha"]
        )

    def test_a_shell_quoted_argument_keeps_its_trailing_punctuation_rule(self):
        self.assertEqual(
            checks.r_arguments("ctest --no-tests=error -R '^t0_alpha$'."), ["t0_alpha"]
        )
        self.assertEqual(
            checks.r_arguments("ctest --no-tests=error -R 't0_alpha'"), ["t0_alpha"]
        )

    def test_an_unbalanced_quote_is_left_as_written(self):
        """A quote with no partner is not a quoted argument. It must keep
        failing the pool lookup rather than being repaired into a name."""
        self.assertEqual(
            checks.r_arguments("ctest --no-tests=error -R '^t0_alpha$"), ["'^t0_alpha$"]
        )
        self.assertEqual(
            checks.r_arguments("ctest --no-tests=error -R \"^t0_alpha$'"),
            ['"^t0_alpha$'],
        )

    def test_an_empty_anchor_pair_strips_to_the_empty_name(self):
        """`-R ^$` is the argument that escaped the ERROR gate. The strip itself
        is correct; what follows it is where the defect was."""
        self.assertEqual(checks.r_arguments("ctest --no-tests=error -R ^$"), [""])


class EmptyRArgumentTest(unittest.TestCase):
    """`-R ^$` must not escape the ERROR gate.

    `files_name_pool()` takes `rsplit(".", 1)[0]` of every basename, and a
    `Files:` entry naming a DIRECTORY has an empty basename, so an unguarded
    pool holds the empty string. `-R ^$` then resolves, `checks` downgrades to
    a WARNING and `registrar` goes silent. An empty name is created by no
    `Files:` line, and the pool says so.
    """

    def test_the_name_pool_holds_no_empty_name(self):
        doc = load_fixture("neg_check_empty_r_argument.md")

        self.assertEqual(
            sorted(doc.files_name_pool()),
            [
                "CMakeLists",
                "CMakeLists.txt",
                "captures/",
                "t0_alpha",
                "t0_alpha.cpp",
                "tests/CMakeLists",
                "tests/CMakeLists.txt",
                "tests/t0_alpha",
                "tests/t0_alpha.cpp",
            ],
        )

    def test_an_empty_r_argument_is_reported_as_created_by_no_files_line(self):
        result = run("neg_check_empty_r_argument.md")

        self.assertEqual(
            pairs(result),
            [
                (
                    "r-name-not-created",
                    "AAA-1",
                    "-R ; no `Files:` line creates that name",
                )
            ],
        )
        self.assertEqual([f.severity for f in result.findings], ["ERROR"])


class CommandExtractionTest(unittest.TestCase):
    def test_a_backticked_invocation_is_one_command(self):
        self.assertEqual(
            checks.commands_in("Run `ctest --test-dir build --no-tests=error -R t0_a` now."),
            ["ctest --test-dir build --no-tests=error -R t0_a"],
        )

    def test_an_unbackticked_invocation_is_still_a_command(self):
        self.assertEqual(
            checks.commands_in("Run ctest --test-dir build -R t0_a and report."),
            ["ctest --test-dir build -R t0_a and report."],
        )

    def test_the_word_ctest_in_running_prose_is_not_a_command(self):
        """`ORC-1's ctest half runs in the fork` is prose. Reading it as an
        unflagged invocation is a false positive in exactly the direction that
        trains a reader to ignore the lint."""
        self.assertEqual(
            checks.commands_in(
                "ORC-1's ctest half runs in the fork and its pytest half asserts "
                "the two are byte-identical."
            ),
            [],
        )

    def test_a_bare_backticked_command_word_is_not_an_invocation(self):
        """`A \x60ctest\x60 invocation carries no \x60--no-tests=error\x60` is the plan
        stating a rule, not running a command."""
        self.assertEqual(
            checks.commands_in("A `ctest` invocation carries no `--no-tests=error`."),
            [],
        )

    def test_an_unbackticked_invocation_needs_a_flag_to_count(self):
        self.assertEqual(checks.commands_in("Run ctest -N to list them."), ["ctest -N to list them."])
        self.assertEqual(checks.commands_in("The cmake step of the board track."), [])

    def test_a_chained_command_is_one_string_and_keeps_every_argument(self):
        self.assertEqual(
            checks.commands_in(
                "`cmake --build build --target core_tests && "
                "ctest --test-dir build --no-tests=error -R t0_a`"
            ),
            [
                "cmake --build build --target core_tests && "
                "ctest --test-dir build --no-tests=error -R t0_a"
            ],
        )

    def test_r_arguments_are_extracted_and_stripped_of_trailing_punctuation(self):
        self.assertEqual(
            checks.r_arguments("ctest --no-tests=error -R t0_a --output-on-failure"),
            ["t0_a"],
        )
        self.assertEqual(checks.r_arguments("ctest --no-tests=error -R t0_a."), ["t0_a"])


class CheckLintTest(unittest.TestCase):
    def test_the_clean_plan_reports_nothing(self):
        result = run("clean_plan.md")

        self.assertEqual(result.findings, [])
        # The task checks and the milestone command.
        self.assertEqual(result.examined, 9)

    def test_the_multiline_and_transcript_fixture_reports_nothing(self):
        result = run("pos_check_multiline_transcript.md")

        self.assertEqual(result.findings, [])

    def test_every_command_defect_is_reported_and_nothing_else(self):
        result = run("neg_check_commands.md")

        self.assertEqual(
            pairs(result),
            [
                (
                    "ctest-forwards-arguments",
                    "AAA-3",
                    "ctest --test-dir build --no-tests=error -R t0_gamma -- --group move",
                ),
                (
                    "ctest-without-no-tests-error",
                    "AAA-2",
                    "ctest --test-dir build -R t0_beta",
                ),
                (
                    "r-name-not-created",
                    "AAA-1",
                    "-R t0_ghost; no `Files:` line creates that name",
                ),
                (
                    "r-name-not-registered",
                    "AAA-5",
                    "-R t0_epsilon; no `add_test(NAME t0_epsilon ...)` appears in this plan",
                ),
                (
                    "target-not-created",
                    "AAA-4",
                    "--target ghost_target; no `Files:` line creates that target",
                ),
            ],
        )

    def test_every_command_defect_carries_its_stated_severity(self):
        result = run("neg_check_commands.md")

        self.assertEqual(
            sorted((f.rule, f.severity) for f in result.findings),
            [
                ("ctest-forwards-arguments", "ERROR"),
                ("ctest-without-no-tests-error", "ERROR"),
                ("r-name-not-created", "ERROR"),
                # Section 7.7 clause 2 needs a build tree. Read from the document
                # it is a statement about the plan, so it warns and does not error.
                ("r-name-not-registered", "WARNING"),
                ("target-not-created", "ERROR"),
            ],
        )

    def test_a_created_test_file_that_no_check_invokes_is_reported(self):
        result = run("neg_check_orphan_test.md")

        self.assertEqual(
            pairs(result),
            [
                (
                    "test-file-never-invoked",
                    "AAA-1",
                    "`test/t1_egress.cpp` is created and no `Check:` line names "
                    "`-R t1_egress`",
                ),
                (
                    "test-file-never-invoked",
                    "AAA-1",
                    "`tests/test_orphan.py` is created and no `Check:` line runs "
                    "`pytest` against it",
                ),
            ],
        )

    def test_the_prefix_allow_list_exempts_the_argument_and_not_the_test_file(self):
        result = run("neg_check_orphan_test.md")

        # `-R t1_` is allow-listed, so it is not reported as an uncreated name.
        self.assertNotIn("r-name-not-created", {f.rule for f in result.findings})
        # It does not count as an invocation of `t1_egress`, which is reported.
        self.assertIn(
            "test-file-never-invoked",
            {f.rule for f in result.findings if "t1_egress" in f.evidence},
        )

    def test_an_unlisted_repository_and_an_unowned_shared_path_are_reported(self):
        result = run("neg_check_repos_and_paths.md")

        self.assertEqual(
            pairs(result),
            [
                (
                    "repository-not-in-layout",
                    "AAA-2",
                    "names `axiomantic/ghost`; section 3.1's table does not carry it",
                ),
                (
                    "shared-path-without-owner",
                    "",
                    "`source/nord/g2/g2Lib/CMakeLists.txt` is claimed by AAA-1, AAA-2; "
                    "section 7.4.2 names no owner for it",
                ),
            ],
        )

    def test_a_document_with_no_command_in_scope_is_a_hard_error(self):
        result = checks.run(
            PlanDocument.from_text(
                "**AAA-1 · A task** — T0\n"
                "Files: `src/one.cpp`\n"
                "Depends: none\n"
                "Check: The operator confirms the repository exists or fails.\n",
                name="inline",
            )
        )

        self.assertEqual(
            [(f.rule, f.message) for f in result.findings],
            [("no-input", "the check lint examined 0 commands in scope")],
        )
        self.assertEqual(result.examined, 0)


class RegistrationScopeTest(unittest.TestCase):
    """Section 1.3 rule 9 says *some task* registers the name.

    The clause names a task, so the `add_test(NAME ...)` scan must read task
    blocks and nothing else. A document-wide scan is a rule a sentence can talk
    out of a finding: a §24.6 defect-register row quoting a registration silences
    the check for a test that no task registers, and the register row is not a
    task. The pair below differs in ONE thing — which side of a task boundary the
    identical sentence sits on.
    """

    def test_a_registration_inside_a_task_block_satisfies_the_rule(self):
        result = run("neg_check_registration_outside_task.md")

        self.assertEqual(
            [f.evidence for f in result.findings if f.task == "BBB-1"],
            [],
        )

    def test_a_registration_only_outside_every_task_block_is_reported(self):
        result = run("neg_check_registration_outside_task.md")

        self.assertEqual(
            pairs(result),
            [
                (
                    "r-name-not-registered",
                    "BBB-2",
                    "-R t0_outside; no `add_test(NAME t0_outside ...)` appears in this plan",
                ),
            ],
        )

    def test_the_scan_reads_task_bodies_and_not_the_whole_document(self):
        doc = load_fixture("neg_check_registration_outside_task.md")

        self.assertEqual(checks.registered_names(doc), {"t0_inside"})


class AbbreviatedSharedPathTest(unittest.TestCase):
    """Section 7.4.2's criterion, with rules B and C expanded.

    Two tasks that spell one file two ways collide. A criterion that compares
    the written strings reports nothing, which is the shape a real collision
    hides behind — `g2Lib/transportHub.cpp`, claimed by SCH-29 through a rule C
    ellipsis and by PROTO-10 in full.
    """

    def test_two_spellings_of_one_file_are_one_collision(self):
        result = run("neg_path_abbreviation.md")
        evidence = [f.evidence for f in result.findings if f.rule == "shared-path-without-owner"]
        self.assertIn(
            "`source/nord/g2/g2Lib/shared.cpp` is claimed by CCC-1, CCC-2; "
            "section 7.4.2 names no owner for it",
            evidence,
        )

    def test_an_ellipsis_claim_collides_with_a_full_spelling(self):
        result = run("neg_path_abbreviation.md")
        evidence = [f.evidence for f in result.findings if f.rule == "shared-path-without-owner"]
        self.assertIn(
            "`source/nord/g2/g2Lib/ellipsed.cpp` is claimed by DDD-1, DDD-2; "
            "section 7.4.2 names no owner for it",
            evidence,
        )

    def test_a_directory_owner_row_silences_the_collision_beneath_it(self):
        result = run("neg_path_abbreviation.md")
        evidence = " ".join(
            f.evidence for f in result.findings if f.rule == "shared-path-without-owner"
        )
        # The rule must still fire on this fixture. If it fires on nothing, the
        # haystack is empty and the assertion below passes for the wrong reason,
        # which is exactly what a lint that collapsed to silence would look like.
        self.assertIn("g2Lib/shared.cpp", evidence)
        self.assertNotIn("g2JucePlugin/covered.cpp", evidence)


class CheckTargetsTest(unittest.TestCase):
    def test_check_targets_matching_set_equality(self):
        doc = PlanDocument.from_text(
            "**AAA-1 · A task** — T0\n"
            "Files: `tests/t0_alpha.cpp`\n"
            "Depends: none\n"
            "Check: `ctest --test-dir build --no-tests=error -R ^t0_alpha$`\n"
            "**BBB-1 · Pytest task** — T0\n"
            "Files: `tests/test_foo.py`\n"
            "Depends: AAA-1\n"
            "Check: `pytest tests/test_foo.py`\n",
            name="inline",
        )
        import tempfile
        with tempfile.NamedTemporaryFile("w+", delete=False) as f:
            f.write("t0_alpha\npytest tests/test_foo.py\n")
            f.flush()
            result = checks.run(doc, check_targets_path=f.name)
            self.assertEqual([f.rule for f in result.findings if f.rule == "check-targets-mismatch"], [])

    def test_check_targets_missing_in_plan(self):
        doc = PlanDocument.from_text(
            "**AAA-1 · A task** — T0\n"
            "Files: `tests/t0_alpha.cpp`\n"
            "Depends: none\n"
            "Check: `ctest --test-dir build --no-tests=error -R ^t0_alpha$`\n",
            name="inline",
        )
        import tempfile
        with tempfile.NamedTemporaryFile("w+", delete=False) as f:
            f.write("t0_alpha\npytest tests/test_missing.py\n")
            f.flush()
            result = checks.run(doc, check_targets_path=f.name)
            mismatches = [f for f in result.findings if f.rule == "check-targets-mismatch"]
            self.assertEqual(len(mismatches), 1)
            self.assertIn("missing in plan: pytest tests/test_missing.py", mismatches[0].evidence)

    def test_check_targets_extra_in_plan(self):
        doc = PlanDocument.from_text(
            "**AAA-1 · A task** — T0\n"
            "Files: `tests/t0_alpha.cpp`\n"
            "Depends: none\n"
            "Check: `ctest --test-dir build --no-tests=error -R ^t0_alpha$`\n",
            name="inline",
        )
        import tempfile
        with tempfile.NamedTemporaryFile("w+", delete=False) as f:
            f.write("# empty check targets\n")
            f.flush()
            result = checks.run(doc, check_targets_path=f.name)
            mismatches = [f for f in result.findings if f.rule == "check-targets-mismatch"]
            self.assertEqual(len(mismatches), 1)
            self.assertIn("extra in plan: t0_alpha", mismatches[0].evidence)


class NonEmptyCheckBlockTest(unittest.TestCase):
    def test_task_block_without_check_block_reports_finding(self):
        doc = PlanDocument.from_text(
            "**AAA-1 · Task no check** — T0\n"
            "Files: `src/one.cpp`\n"
            "Depends: none\n",
            name="inline",
        )
        result = checks.run(doc)
        findings = [f for f in result.findings if f.rule == "non-empty-check-block"]
        self.assertEqual(len(findings), 1)
        self.assertIn("carries no Check: block", findings[0].message)

    def test_check_block_without_command_or_failure_mechanism_reports_finding(self):
        doc = PlanDocument.from_text(
            "**AAA-1 · Task manual check** — T0\n"
            "Files: `src/one.cpp`\n"
            "Depends: none\n"
            "Check: The engineer verifies that the output looks good.\n",
            name="inline",
        )
        result = checks.run(doc)
        findings = [f for f in result.findings if f.rule == "non-empty-check-block"]
        self.assertEqual(len(findings), 1)
        self.assertIn("no explicit failure mechanism", findings[0].message)

    def test_check_block_with_explicit_failure_mechanism_passes(self):
        doc = PlanDocument.from_text(
            "**AAA-1 · Task explicit failure** — T0\n"
            "Files: `src/one.cpp`\n"
            "Depends: none\n"
            "Check: The script verifies output and fails on mismatch.\n",
            name="inline",
        )
        result = checks.run(doc)
        findings = [f for f in result.findings if f.rule == "non-empty-check-block"]
        self.assertEqual(findings, [])


class BuildDirTest(unittest.TestCase):
    def test_build_dir_nonexistent_or_lacking_ctestfile_is_hard_failure(self):
        doc = PlanDocument.from_text(
            "**AAA-1 · A task** — T0\n"
            "Files: `tests/t0_alpha.cpp`\n"
            "Depends: none\n"
            "Check: `ctest --test-dir build --no-tests=error -R ^t0_alpha$`\n",
            name="inline",
        )
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            # Empty directory without CTestTestfile.cmake
            result = checks.run(doc, build_dirs=[f"axiomantic/nord-g2={tmp}"])
            findings = [f for f in result.findings if f.rule == "invalid-build-dir"]
            self.assertEqual(len(findings), 1)
            self.assertEqual(findings[0].severity, "ERROR")
            self.assertIn("lacks CTestTestfile.cmake", findings[0].message)

        # Nonexistent directory
        result = checks.run(doc, build_dirs=["axiomantic/nord-g2=/nonexistent/build/dir"])
        findings = [f for f in result.findings if f.rule == "invalid-build-dir"]
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].severity, "ERROR")

    def test_build_dir_invalid_format(self):
        doc = PlanDocument.from_text(
            "**AAA-1 · A task** — T0\n"
            "Files: `tests/t0_alpha.cpp`\n"
            "Depends: none\n"
            "Check: `ctest --test-dir build --no-tests=error -R ^t0_alpha$`\n",
            name="inline",
        )
        result = checks.run(doc, build_dirs=["no_equals_sign_here"])
        findings = [f for f in result.findings if f.rule == "invalid-build-dir"]
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].severity, "ERROR")
        self.assertIn("invalid --build-dir format", findings[0].message)

    def test_build_dir_valid_with_matching_registered_test_passes(self):
        doc = PlanDocument.from_text(
            "**AAA-1 · A task** — T0\n"
            "Files: `tests/t0_alpha.cpp`\n"
            "Depends: none\n"
            "Check: `ctest --test-dir build --no-tests=error -R ^t0_alpha$`\n",
            name="inline",
        )
        import pathlib
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            p = pathlib.Path(tmp)
            (p / "CTestTestfile.cmake").write_text('add_test(t0_alpha "echo" "1")\n')
            result = checks.run(doc, build_dirs=[f"axiomantic/nord-g2={tmp}"])
            reg_findings = [f for f in result.findings if f.rule == "r-name-not-registered"]
            self.assertEqual(reg_findings, [])

    def test_build_dir_valid_with_missing_registered_test_upgrades_to_error(self):
        doc = PlanDocument.from_text(
            "**AAA-1 · A task** — T0\n"
            "Files: `tests/t0_alpha.cpp`\n"
            "Depends: none\n"
            "Check: `ctest --test-dir build --no-tests=error -R ^t0_alpha$`\n",
            name="inline",
        )
        import pathlib
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            p = pathlib.Path(tmp)
            # Register a different test, so t0_alpha is missing from CTest listing
            (p / "CTestTestfile.cmake").write_text('add_test(t0_other "echo" "1")\n')
            result = checks.run(doc, build_dirs=[f"axiomantic/nord-g2={tmp}"])
            reg_findings = [f for f in result.findings if f.rule == "r-name-not-registered"]
            self.assertEqual(len(reg_findings), 1)
            self.assertEqual(reg_findings[0].severity, "ERROR")
            self.assertIn("missing from CTest listing in build directory", reg_findings[0].evidence)


class MarkedSecondWriteTest(unittest.TestCase):
    """Section 7.4.2, verbatim: "A marked entry never raises
    `shared-path-without-owner`, because a marked entry is not a claim."

    "Not a claim" is stronger than "strip the marker and carry on". An entry
    that carried a marker never enters the claims map at all, so one bare
    writer beside any number of marked ones is one claimant and not two. The
    weaker reading — strip the marker, then count the entry — leaves the rule
    firing on `unrowed_manifest.cpp` below, which is why that path is in the
    fixture.

    The first case is the control. `genuinely_unowned.cpp` has two bare
    claimants and no owner row, and it must stay red. A rule that reads the
    marker and goes silent everywhere was deleted, not repaired, and a fixture
    on which nothing fires proves nothing about the three that go silent.
    """

    FIXTURE = "neg_check_marked_second_write.md"

    def verdict_for(self, path):
        """Every `shared-path-without-owner` evidence naming exactly this path.

        The comparison is a whole list against a whole list, so an extra
        finding fails as loudly as a missing one.
        """
        result = run(self.FIXTURE)
        return [
            f.evidence
            for f in result.findings
            if f.rule == "shared-path-without-owner"
            and f.evidence.startswith(f"`{path}`")
        ]

    def test_a_bare_collision_with_no_owner_row_is_reported(self):
        """THE CONTROL. Red before the marker is understood and red after."""
        self.assertEqual(
            self.verdict_for("source/nord/g2/g2Lib/genuinely_unowned.cpp"),
            [
                "`source/nord/g2/g2Lib/genuinely_unowned.cpp` is claimed by "
                "AAA-2, AAA-3; section 7.4.2 names no owner for it"
            ],
        )

    def test_a_bare_collision_with_an_owner_row_is_silent(self):
        self.assertEqual(self.verdict_for("source/nord/g2/g2Lib/owned_shared.cpp"), [])

    def test_a_marked_entry_with_an_owner_row_is_not_a_claim(self):
        """The defect. The marked spelling was a claims-map key of its own, two
        tasks carried it, and no owner row can name a path with a marker on the
        end of it — so the owner row that exists could not be found."""
        self.assertEqual(
            self.verdict_for("source/nord/g2/g2Lib/test/tests_marked.cmake"),
            [],
        )
        self.assertEqual(
            self.verdict_for("source/nord/g2/g2Lib/test/tests_marked.cmake@AAA-1"),
            [],
        )

    def test_a_marked_entry_with_no_owner_row_is_not_a_claim_either(self):
        """The discriminator between the two readings. One bare writer and two
        marked ones on a path section 7.4.2 holds no row for: "never a claim"
        gives one claimant and silence, "strip and count" gives three claimants
        and a finding. Section 7.4.2 gives the missing row to
        `second-write-no-owner-row`, a rule this tool does not implement."""
        self.assertEqual(
            self.verdict_for("source/nord/g2/g2Lib/unrowed_manifest.cpp"),
            [],
        )
        self.assertEqual(
            self.verdict_for("source/nord/g2/g2Lib/unrowed_manifest.cpp@AAA-1"),
            [],
        )

    def test_the_whole_verdict_of_the_rule_on_this_fixture(self):
        """The cases above filter by path, so a finding naming a path none of
        them names would escape every one of them. This one holds the complete
        finding — rule, task, section, line, severity and evidence — against
        the complete list the lint produced."""
        result = run(self.FIXTURE)
        first_claimant = load_fixture(self.FIXTURE).task("AAA-2")

        self.assertEqual(
            [
                (f.rule, f.task, f.section, f.line, f.severity, f.evidence)
                for f in result.findings
                if f.rule == "shared-path-without-owner"
            ],
            [
                (
                    "shared-path-without-owner",
                    "",
                    "7.4.2 Every shared file has one owner",
                    first_claimant.line,
                    ERROR,
                    "`source/nord/g2/g2Lib/genuinely_unowned.cpp` is claimed by "
                    "AAA-2, AAA-3; section 7.4.2 names no owner for it",
                )
            ],
        )


if __name__ == "__main__":
    unittest.main()

