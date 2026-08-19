"""Mutation check, per RULE.

Break one thing in the clean fixture and assert the exact set of RULES that go
red. Not the lint that owns them — the rules.

The distinction is the whole point of this file. An earlier revision asserted
which LINT reddened, and a rule can be dead code with the suite fully green when
the same mutation collaterally trips another rule inside the same lint.

The properties asserted here:

  * every mutation reddens EXACTLY the rules named beside it, so disabling any
    one rule makes at least one subtest fail, and the failure names the rule;
  * every rule the document lints can emit has a mutation. The rule set is read
    from the lint SOURCE, not from a list kept by hand, so a rule added to a
    lint with no mutation beside it fails this file.

The `payload` lint reads a repository tree and not the plan, so its equivalent
is the pair of fixture trees in `test_payload.py`.
"""

import ast
import pathlib
import unittest

from tests.planlint.support import fixture_path

from planlint import (
    anchors,
    checks,
    closure,
    counts,
    graph,
    implicit,
    registrar,
    structure,
    tiers,
    waves,
)
from planlint.document import PlanDocument

LINTS = {
    "structure": structure.run,
    "anchors": anchors.run,
    "graph": graph.run,
    "waves": waves.run,
    "tiers": tiers.run,
    "checks": checks.run,
    "counts": counts.run,
    "implicit": implicit.run,
    "registrar": registrar.run,
    "closure": closure.run,
}

CLEAN = fixture_path("clean_plan.md").read_text(encoding="utf-8")
CLEAN_CHECK_TARGETS = fixture_path("clean_check_targets.txt")

# The rules the document lints emit. The list is here so that adding or
# renaming a rule is a deliberate edit to this file and not a silent drift; the
# meta-test reads the same set out of the lint source and compares.
DOCUMENT_RULES = frozenset(
    {
        # anchors
        "derived-figure-stale",
        "derived-figure-unanchored",
        "derived-figure-unknown-key",
        "derived-figure-unparsed",
        # graph
        "dependency-cycle",
        "depends-prose",
        "self-loop",
        "unknown-dependency",
        # waves
        "task-without-wave",
        "wave-order",
        "wave-without-task",
        # tiers
        "missing-tier",
        "range-holds-conditional",
        "range-holds-higher-tier",
        "t0-depends-t1",
        "t0-gated-check",
        "t0-reads-private-fixture",
        # checks
        "check-targets-mismatch",
        "ctest-forwards-arguments",
        "ctest-without-no-tests-error",
        "invalid-build-dir",
        "non-empty-check-block",
        "r-name-not-created",
        "r-name-not-registered",
        "repository-not-in-layout",
        "shared-path-without-owner",
        "target-not-created",
        "test-file-never-invoked",
        # counts
        "conditional-count-mismatch",
        "cross-track-edge-count-mismatch",
        "cross-track-edge-missing-from-7-4",
        "cross-track-edge-not-in-graph",
        "cross-track-edge-not-in-graph-across-waves",
        "cross-track-edge-undeclared",
        "cross-track-row-7-4-not-in-graph",
        "cross-track-row-7-4-not-in-graph-across-waves",
        "total-count-mismatch",
        "total-is-not-the-sum",
        "track-count-mismatch",
        # implicit
        "implicit-dependency",
        "implicit-dependency-would-cycle",
        # registrar
        "creator-outside-closure",
        "registrar-outside-closure",
        "registrar-unknown",
        # closure
        "gated-symbol-without-enabler",
        "header-producer-unreachable",
        "symbol-closure-candidate",
        "symbol-producer-unreachable",
        "target-producer-unreachable",
        # structure
        "done-marker-not-line-anchored",
        "unclosed-fence",
        "unmatched-backtick",
    }
)

# (label, the text replaced, the text that replaces it, the rules that must go
# red — exactly those and no others). Ordered by the lint that owns the rule.
MUTATIONS = [
    # ------------------------------------------------------------------ graph
    (
        "a dependency cycle between two tasks of one wave",
        "Depends: AAA-2. **CONDITIONAL: this task exists only if the probe "
        "reports a second result.**",
        "Depends: CCC-1. **CONDITIONAL: this task exists only if the probe "
        "reports a second result.**",
        # The edit takes AAA-2 off CCC-2's line, and section 7.3's column still
        # states `CCC-2 → AAA-2`. Those two ends sit in different waves, so the
        # in-wave rule is silent and the across-waves one is what sees it.
        {"dependency-cycle", "cross-track-edge-not-in-graph-across-waves"},
    ),
    (
        "a task naming itself",
        "Depends: none",
        "Depends: AAA-1",
        {"self-loop"},
    ),
    (
        "a Depends line naming an identifier the plan defines nowhere",
        "Depends: AAA-1\nCheck: `ctest --test-dir build --no-tests=error -R t0_beta`",
        "Depends: AAA-1, ZZZ-9\n"
        "Check: `ctest --test-dir build --no-tests=error -R t0_beta`",
        {"unknown-dependency"},
    ),
    (
        "a scheduling note on a Depends line",
        "Depends: AAA-1\nCheck: `ctest --test-dir build --no-tests=error -R t0_beta`",
        "Depends: AAA-1. Scheduled before BBB-1.\n"
        "Check: `ctest --test-dir build --no-tests=error -R t0_beta`",
        {"depends-prose"},
    ),
    # ------------------------------------------------------------------ waves
    (
        "a task the wave table places in no row",
        "| 1 | 1 | AAA-1 |",
        "| 1 | 1 | none |",
        {"task-without-wave"},
    ),
    (
        "a wave row naming a task no block defines",
        "| 4 | 4 | EEE-1 |",
        "| 4 | 4 | EEE-1, ZZZ-9 |",
        {"wave-without-task"},
    ),
    (
        "a wave inversion",
        "| 1 | 1 | AAA-1 |\n| 2 | 2 | AAA-2, BBB-1, DDD-1, DDD-2 |\n"
        "| 3 | 3 | CCC-1, CCC-2 |",
        "| 2 | 2 | AAA-2, BBB-1, DDD-1, DDD-2 |\n| 3 | 3 | CCC-1, CCC-2, AAA-1 |",
        {"wave-order"},
    ),
    # ------------------------------------------------------------------ tiers
    (
        "a header with the tier stripped off",
        "**BBB-1 · The gated read** — T1",
        "**BBB-1 · The gated read**",
        {"missing-tier"},
    ),
    (
        "a T0 check gated on the firmware artifact",
        "-R t0_beta`. Registered",
        "-R t0_beta` with `NMG2_ARTIFACTS` set. Registered",
        {"t0-gated-check"},
    ),
    (
        "a T0 check reading a fixture the register marks PRIVATE",
        "carries one negative case that drives it to fail.",
        "carries one negative case that drives it to fail. It reads "
        "`dumps/session.log`.",
        {"t0-reads-private-fixture"},
    ),
    (
        "a T0 task waiting on a T1 task",
        "Depends: CCC-2, AAA-2.",
        "Depends: CCC-2, BBB-1.",
        # AAA-2 comes off CCC-1's line, and both stated sites still carry
        # `CCC-1 → AAA-2` across a wave boundary.
        {
            "t0-depends-t1",
            "cross-track-edge-not-in-graph-across-waves",
            "cross-track-row-7-4-not-in-graph-across-waves",
        },
    ),
    (
        "a Depends range swallowing a higher tier",
        "Depends: AAA-2\nCheck: `ctest --test-dir build --no-tests=error -R t1_gamma`",
        "Depends: DDD-1 to DDD-2\n"
        "Check: `ctest --test-dir build --no-tests=error -R t1_gamma`",
        {
            "range-holds-higher-tier",
            "derived-figure-stale",
            "cross-track-edge-count-mismatch",
            "cross-track-edge-not-in-graph",
            "cross-track-edge-undeclared",
            "cross-track-edge-missing-from-7-4",
            "cross-track-row-7-4-not-in-graph",
        },
    ),
    (
        "a Depends range swallowing a conditional task",
        "Depends: CCC-1, CCC-2",
        "Depends: CCC-1 to CCC-2",
        {"range-holds-conditional"},
    ),
    # ----------------------------------------------------------------- checks
    (
        "the milestone command losing --no-tests=error",
        "--target core_tests && ctest --test-dir build --no-tests=error -R ^t0_alpha$",
        "--target core_tests && ctest --test-dir build -R ^t0_alpha$",
        {"ctest-without-no-tests-error"},
    ),
    (
        "a -- argument forwarding form",
        "-R t0_delta`. Registered",
        "-R t0_delta -- --group move`. Registered",
        {"ctest-forwards-arguments"},
    ),
    (
        "an -R argument no Files line creates",
        "-R t0_beta`. Registered",
        "-R t0_beta` and `ctest --test-dir build --no-tests=error -R t0_ghost`. "
        "Registered",
        {"r-name-not-created", "registrar-unknown", "check-targets-mismatch"},
    ),
    (
        "an -R argument that strips to the empty name",
        "-R t0_beta`. Registered",
        "-R ^$`. Registered",
        {"r-name-not-created", "registrar-unknown", "test-file-never-invoked", "check-targets-mismatch"},
    ),
    (
        "a name the plan states no add_test for",
        "add_test(NAME t0_epsilon ...)",
        "add_test(NAME t0_theta ...)",
        {"r-name-not-registered"},
    ),
    (
        "a --target no Files line creates",
        "--target core_tests",
        "--target ghost_target",
        {"target-not-created"},
    ),
    (
        "a test file nothing invokes",
        "Files: `testdata/synth/`, `testdata/shared.json`, `tests/t0_beta.cpp`",
        "Files: `testdata/synth/`, `testdata/shared.json`, `tests/t0_beta.cpp`, "
        "`tests/t0_orphan.cpp`",
        {"test-file-never-invoked"},
    ),
    (
        "a task naming a repository section 3.1's table does not carry",
        "The work lands in the `axiomantic/core` repository.",
        "The work lands in the `axiomantic/ghost` repository.",
        {"repository-not-in-layout"},
    ),
    (
        "a shared path whose directory owner row stops covering it",
        "| `g2Lib/test/` | AAA-1 |",
        "| `g2Lib/other/` | AAA-1 |",
        {"shared-path-without-owner"},
    ),
    (
        "a task block with no Check block",
        "Check: `ctest --test-dir build --no-tests=error -R t0_beta`. Registered with `add_test(NAME t0_beta ...)` through the track test list.",
        "Design: 2.1",
        {"non-empty-check-block", "check-targets-mismatch", "test-file-never-invoked"},
    ),
    (
        "a Check target missing from check-targets.txt",
        "Check: `ctest --test-dir build --no-tests=error -R t0_beta`. Registered with `add_test(NAME t0_beta ...)` through the track test list.",
        "Check: `ctest --test-dir build --no-tests=error -R t0_ghost`. Registered with `add_test(NAME t0_ghost ...)` through the track test list.",
        {"check-targets-mismatch", "r-name-not-created", "registrar-unknown", "test-file-never-invoked"},
    ),
    (
        "an invalid build-dir path",
        "Check: `ctest --test-dir build --no-tests=error -R t0_beta`",
        "Check: `ctest --test-dir build --no-tests=error -R t0_beta`",
        {"invalid-build-dir"},
        ["axiomantic/nord-g2=/nonexistent/path/to/build"],
    ),
    # ----------------------------------------------------------------- counts
    (
        "two track rows that miscount their tracks and still sum to the total",
        "| Alpha (AAA) | 2 |\n| Beta (BBB) | 1 |",
        "| Alpha (AAA) | 3 |\n| Beta (BBB) | 0 |",
        {"track-count-mismatch"},
    ),
    (
        "a total row that miscounts the document",
        "| **Total task blocks** | **8** |",
        "| **Total task blocks** | **9** |",
        {"total-count-mismatch", "total-is-not-the-sum"},
    ),
    (
        "a track row repeated, so the rows sum past a correct total",
        "| Epsilon (EEE) | 1 |",
        "| Epsilon (EEE) | 1 |\n| Epsilon (EEE) | 1 |",
        {"total-is-not-the-sum"},
    ),
    (
        "a conditional-task count section 24.4's table does not hold",
        "Of the two conditional tasks",
        "Of the three conditional tasks",
        {"conditional-count-mismatch"},
    ),
    (
        "a cross-track edge count the `Depends:` graph does not hold",
        "There are two edges",
        "There are three edges",
        {"cross-track-edge-count-mismatch"},
    ),
    (
        "an in-wave cross-track edge struck out of section 7.3's column",
        "| Delta | Alpha | DDD-1 → AAA-2 |",
        "| Delta | Alpha | — |",
        {"cross-track-edge-undeclared"},
    ),
    (
        "a section 7.3 row for an edge no `Depends:` line declares",
        "| Epsilon | Gamma | EEE-1 → CCC-1, CCC-2 |",
        "| Epsilon | Gamma | EEE-1 → CCC-1, CCC-2 |\n| Beta | Delta | BBB-1 → DDD-1 |",
        {"cross-track-edge-not-in-graph"},
    ),
    (
        "an in-wave cross-track edge struck out of section 7.4's table",
        "| Beta | BBB-1 | Alpha | AAA-2 | header |",
        "| Beta | — | Alpha | AAA-2 | header |",
        {"cross-track-edge-missing-from-7-4"},
    ),
    (
        "a section 7.4 row for an edge no `Depends:` line declares",
        "| Gamma | CCC-1 | Alpha | AAA-2 | behaviour | 3 → 2 |",
        "| Gamma | CCC-1 | Alpha | AAA-2 | behaviour | 3 → 2 |\n"
        "| Beta | BBB-1 | Delta | DDD-1 | behaviour | **2 → 2, inside one wave** |",
        {"cross-track-row-7-4-not-in-graph"},
    ),
    (
        "a section 7.3 row for an edge across waves no `Depends:` line declares",
        "| Epsilon | Gamma | EEE-1 → CCC-1, CCC-2 |",
        "| Epsilon | Gamma | EEE-1 → CCC-1, CCC-2 |\n| Epsilon | Alpha | EEE-1 → AAA-1 |",
        {"cross-track-edge-not-in-graph-across-waves"},
    ),
    (
        "a section 7.4 row for an edge across waves no `Depends:` line declares",
        "| Gamma | CCC-1 | Alpha | AAA-2 | behaviour | 3 → 2 |",
        "| Gamma | CCC-1 | Alpha | AAA-2 | behaviour | 3 → 2 |\n"
        "| Epsilon | EEE-1 | Alpha | AAA-1 | behaviour | 4 → 1 |",
        {"cross-track-row-7-4-not-in-graph-across-waves"},
    ),
    # ---------------------------------------------------------------- anchors
    (
        "an anchored restatement of a figure the graph no longer holds",
        "-->two of them.",
        "-->three of them.",
        {"derived-figure-stale"},
    ),
    (
        "an anchored token that is no number this tool reads",
        "-->two of them.",
        "-->several of them.",
        {"derived-figure-unparsed"},
    ),
    (
        "an anchor whose key names a figure the tool does not compute",
        "derived: cross-track-edge-count -->two",
        "derived: cross-track-edge-kount -->two",
        {"derived-figure-unknown-key", "derived-figure-unanchored"},
    ),
    # --------------------------------------------------------------- implicit
    (
        "an artifact read with no declared edge",
        "-R t0_delta`. Registered",
        "-R t0_delta` reads `testdata/beta/`. Registered",
        {"implicit-dependency"},
    ),
    (
        "an artifact read whose missing edge would close a cycle",
        "carries one negative case that drives it to fail.",
        "carries one negative case that drives it to fail. It reads "
        "`testdata/synth/`.",
        {"implicit-dependency-would-cycle"},
    ),
    # -------------------------------------------------------------- registrar
    (
        "a creator moved out of the depending task's closure",
        "-R t0_beta`. Registered",
        "-R t0_beta` and `ctest --test-dir build --no-tests=error -R t0_delta`. "
        "Registered",
        {"creator-outside-closure"},
    ),
    (
        "a registrar moved out of the depending task's closure",
        "Depends: AAA-2\nCheck: `ctest --test-dir build --no-tests=error -R t1_gamma`",
        "Depends: none\nCheck: `ctest --test-dir build --no-tests=error -R t1_gamma`",
        {
            "registrar-outside-closure",
            "derived-figure-stale",
            "cross-track-edge-count-mismatch",
            "cross-track-edge-not-in-graph",
            "cross-track-row-7-4-not-in-graph",
        },
    ),
    # ---------------------------------------------------------------- closure
    (
        "a link on a build target the linking task cannot reach",
        "The suite carries a failing case of its own.",
        "The suite carries a failing case of its own. It links `gamma::gamma_lib`.",
        {"target-producer-unreachable"},
    ),
    (
        "a check that reads a type the reading task cannot reach",
        "`add_test(NAME t2_zeta ...)`.",
        "`add_test(NAME t2_zeta ...)`. Its gate reads `Gamma::Config`.",
        {"symbol-producer-unreachable"},
    ),
    (
        "an include of a header the including task cannot reach",
        "`add_test(NAME t1_gamma ...)`.",
        "`add_test(NAME t1_gamma ...)`. The translation unit carries "
        '`#include "gamma.h"`.',
        {"header-producer-unreachable"},
    ),
    (
        "a call on a symbol behind an option the calling task never turns on",
        "`add_test(NAME t0_delta ...)`.",
        "`add_test(NAME t0_delta ...)`. It calls `gamma_lib_start`.",
        {"gated-symbol-without-enabler"},
    ),
    (
        "an unreachable consumption whose own sentence hedges",
        "with `NMG2_ARTIFACTS` set.",
        "with `NMG2_ARTIFACTS` set. This task does not link `gamma::gamma_lib`.",
        {"symbol-closure-candidate"},
    ),
    # -------------------------------------------------------------- structure
    (
        "a task body carrying a backtick with no partner",
        "The suite carries a failing case of its own.",
        "The suite carries a failing case of its own. The forwarding flag is "
        "spelled `--group.",
        {"unmatched-backtick"},
    ),
    (
        "a completion marker written behind a lead-in",
        "`add_test(NAME t0_eta ...)`.",
        "`add_test(NAME t0_eta ...)`.\nNote: **DONE on 2026-01-01, commit `0000000`.**",
        {"done-marker-not-line-anchored"},
    ),
    (
        "a fenced block opened and never closed",
        "### 24.4 The conditional tasks",
        "```\n\n### 24.4 The conditional tasks",
        {"unclosed-fence"},
    ),
]


def red_rules(text, build_dirs=None):
    """Every rule any document lint reports against a document."""
    doc = PlanDocument.from_text(text, name="mutant")
    out = set()
    for name, run in LINTS.items():
        if name == "checks":
            out |= {
                finding.rule
                for finding in run(doc, check_targets_path=CLEAN_CHECK_TARGETS, build_dirs=build_dirs).findings
            }
        else:
            out |= {finding.rule for finding in run(doc).findings}
    return out


def rules_in_source(module):
    """Every rule a lint module can emit, read from its source.

    Read from the SOURCE and not from a list kept by hand, so that a rule added
    to a lint is a rule this file already knows about. A `Finding` whose rule is
    not a literal is reported rather than skipped: a rule the source cannot name
    is a rule no mutation can cover.
    """
    tree = ast.parse(pathlib.Path(module.__file__).read_text(encoding="utf-8"))
    out = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or getattr(node.func, "id", "") != "Finding":
            continue
        found = [keyword.value for keyword in node.keywords if keyword.arg == "rule"]
        found += node.args[:1]
        for value in found:
            out.add(value.value if isinstance(value, ast.Constant) else ast.unparse(value))
    return out


def rules_the_lints_emit():
    out = set()
    for module in (
        graph, waves, tiers, checks, counts, implicit, registrar, closure,
        structure, anchors,
    ):
        out |= rules_in_source(module)
    return out


class MutationTest(unittest.TestCase):
    def test_the_clean_fixture_is_green_for_every_lint(self):
        self.assertEqual(red_rules(CLEAN), set())

    def test_each_mutation_reddens_exactly_the_rules_that_own_it(self):
        for item in MUTATIONS:
            label, old, new, expected = item[:4]
            build_dirs = item[4] if len(item) > 4 else None
            with self.subTest(mutation=label):
                self.assertIn(old, CLEAN, f"anchor missing for: {label}")
                self.assertEqual(red_rules(CLEAN.replace(old, new, 1), build_dirs=build_dirs), expected)

    def test_every_mutation_anchor_appears_once_in_the_clean_fixture(self):
        """A mutation whose anchor appears twice edits a place its author did
        not read, and its expected rule set then describes the wrong defect."""
        self.assertEqual(
            [item[0] for item in MUTATIONS if CLEAN.count(item[1]) != 1],
            [],
        )


class RuleCoverageTest(unittest.TestCase):
    """The meta-test. A rule with no mutation is a rule that can be dead code
    with this suite fully green, which is the defect class the whole tool exists
    to catch."""

    def covered(self):
        out = set()
        for item in MUTATIONS:
            out |= item[3]
        return out

    def test_the_lints_emit_exactly_the_rules_this_file_names(self):
        self.assertEqual(rules_the_lints_emit(), set(DOCUMENT_RULES))

    def test_every_rule_the_lints_emit_has_a_mutation(self):
        self.assertEqual(sorted(rules_the_lints_emit() - self.covered()), [])

    def test_no_mutation_expects_a_rule_no_lint_emits(self):
        self.assertEqual(sorted(self.covered() - rules_the_lints_emit()), [])

    def test_the_mutation_count_is_the_one_this_file_carries(self):
        self.assertEqual(len(MUTATIONS), 51)

    def test_the_rule_count_is_the_one_the_review_measured(self):
        self.assertEqual(len(rules_the_lints_emit()), 52)

    def test_every_document_lint_owns_at_least_one_covered_rule(self):
        modules = {
            "graph": graph, "waves": waves, "tiers": tiers, "checks": checks,
            "counts": counts, "implicit": implicit, "registrar": registrar,
            "closure": closure, "structure": structure, "anchors": anchors,
        }
        self.assertEqual(
            sorted(
                name
                for name, module in modules.items()
                if not rules_in_source(module) & self.covered()
            ),
            [],
        )


if __name__ == "__main__":
    unittest.main()
