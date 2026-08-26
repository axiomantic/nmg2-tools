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
import tempfile
import types
import unittest

from tests.planlint.support import fixture_path

from planlint import (
    anchors,
    checks,
    closure,
    counts,
    gate,
    graph,
    implicit,
    markers,
    registrar,
    removed,
    secondwrite,
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
    "markers": markers.run,
    "secondwrite": secondwrite.run,
    "removed": removed.run,
    "gate": gate.run,
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
        # markers
        "done-marker-citation-not-in-form",
        "done-marker-path-uncited",
        # secondwrite
        "second-write-class-undecided",
        "second-write-no-owner-row",
        "second-write-outside-class",
        # removed
        "check-predicate-removed-by-default-build",
        "check-verdict-rests-on-an-assertion-not-firing",
        # gate
        "done-marker-over-a-dependency-this-plan-does-not-schedule",
        "done-marker-over-incomplete-dependency",
        # structure
        "done-marker-not-line-anchored",
        "table-column-count-undecided",
        "table-row-column-count",
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
        # Section 5.2 rule 7 admits a T0-to-T1 edge, so the edge alone is not
        # the defect and the mutation must break a conjunct: the check reads a
        # path BBB-1 produces that section 7.8 marks PRIVATE in a repository
        # section 3.1 marks PRIVATE.
        "a T0 task waiting on a T1 task and reading its private output",
        "Depends: CCC-2, AAA-2. **CONDITIONAL: this task exists only if the probe "
        "reports a result.**\nCheck: `ctest --test-dir build --no-tests=error "
        "-R t0_delta`. Registered with `add_test(NAME t0_delta ...)`.",
        "Depends: CCC-2, BBB-1. **CONDITIONAL: this task exists only if the probe "
        "reports a result.**\nCheck: `ctest --test-dir build --no-tests=error "
        "-R t0_delta`. It reads `dumps/session.log`. Registered with "
        "`add_test(NAME t0_delta ...)`.",
        # AAA-2 comes off CCC-1's line, and both stated sites still carry
        # `CCC-1 → AAA-2` across a wave boundary.
        {
            "t0-depends-t1",
            "t0-reads-private-fixture",
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
        "a registration moved out of its task block and into loose prose",
        "Registered with `add_test(NAME t0_epsilon ...)`.\nIt exports",
        "\n\n## An interlude, outside every task\n\n"
        "Registered with `add_test(NAME t0_epsilon ...)`.\n\nIt exports",
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
        # The marker this adds is a REAL marker, so the marker lint sees it too
        # and reports that its citation is not in the per-path form. Both rules
        # are true of the same line and neither subsumes the other: one is about
        # where the marker sits, the other about what its citation states.
        # EEE-1's marker is live and CCC-1 and CCC-2 carry none, so the
        # completion gate reports the pair as a third true statement.
        {
            "done-marker-not-line-anchored",
            "done-marker-citation-not-in-form",
            "done-marker-over-incomplete-dependency",
        },
    ),
    (
        "a fenced block opened and never closed",
        "### 24.4 The conditional tasks",
        "```\n\n### 24.4 The conditional tasks",
        {"unclosed-fence"},
    ),
    (
        "a raw pipe inside a table cell",
        "The core builds and the surface answers.",
        "The core builds and the surface answers | it does.",
        {"table-row-column-count"},
    ),
    (
        "a continuation row detached from the table whose columns it borrows",
        "## 7. The tracks and the dependency graph",
        "| **M2** | A row below a blank line. | T0 | It borrows nothing. |\n"
        "\n"
        "## 7. The tracks and the dependency graph",
        {"table-column-count-undecided"},
    ),
    # ---------------------------------------------------------------- markers
    (
        "a completion marker whose citation leaves a declared path out",
        "`add_test(NAME t2_zeta ...)`.",
        "`add_test(NAME t2_zeta ...)`.\n"
        "**DONE on 2026-01-01, 1 commit. CITED PER DECLARED PATH:** "
        "`axiomantic/core` `1111111` → `tests/t2_zeta.cpp`.",
        # DDD-2's marker is live and DDD-1 carries none, so the completion gate
        # reports the pair as well.
        {"done-marker-path-uncited", "done-marker-over-incomplete-dependency"},
    ),
    (
        # EEE-1 already depends on CCC-1 and CCC-2, so the added task's
        # Depends edge needs no wave or count change; the marked path is one
        # NO owner row names, which is exactly test 1.
        "a marked entry whose path carries no owner row",
        "**EEE-1 · The late gate** — T0\nFiles: `tests/t0_eta.cpp`, `tests/tests_core.cmake`",
        "**EEE-1 · The late gate** — T0\nFiles: `tests/t0_eta.cpp`, `g2Lib/eta_hook.h@CCC-1`, `tests/tests_core.cmake`",
        {"second-write-no-owner-row"},
    ),
    (
        # One contiguous replacement adds BOTH the marked entry and the
        # owner row that refuses it: the row exists on the
        # post-replacement document, so test 1 passes there, but its
        # mechanism cell carries no class sentence -- test 4 refuses the
        # writer. The undecided variant of this shape (a two-column row
        # stating no mechanism at all) is the mutation beside this one.
        "a marked entry whose owner row states no class",
        # Anchored on EEE-1's REAL Files line. The NEW side adds the
        # marked entry and the owner row that refuses it in one edit.
        "**EEE-1 · The late gate** — T0\nFiles: `tests/t0_eta.cpp`, `tests/tests_core.cmake`",
        "**EEE-1 · The late gate** — T0\nFiles: `tests/t0_eta.cpp`, `g2Lib/classless.h@CCC-1`, `tests/tests_core.cmake`\n"
        "| Path | Owner | The mechanism for everybody else |\n|---|---|---|\n"
        "| `g2Lib/classless.h` | **CCC-1** | Ask CCC-1 before editing. |",
        {"second-write-outside-class"},
    ),
    (
        # EEE-1's Files line gains the marked entry. The tests_core owner
        # row is TWO-COLUMN in the clean fixture, so it states no mechanism
        # at all -- the undecided branch, not the refusal. The refusal
        # branch (a mechanism column present with no class sentence in it)
        # is covered by the inline fixtures in test_secondwrite, which
        # build the four-column shape directly; a mutation here would have
        # to widen a table and edit a task in one non-contiguous
        # replacement, which the harness cannot express.
        "a marked entry whose owner row states no mechanism",
        "Files: `tests/t0_eta.cpp`, `tests/tests_core.cmake`",
        "Files: `tests/t0_eta.cpp`, `tests/tests_core.cmake@AAA-1`",
        {"second-write-class-undecided"},
    ),
    # ---------------------------------------------------------------- removed
    (
        # The clause names the MECHANISM `NDEBUG` deletes, and the block names
        # no build type that keeps it. The English verb `asserts` is not the
        # subject: it is what a test does in every build.
        "a Check: predicate resting on a mechanism the default build removes",
        "The suite carries a failing case of its own.",
        "The suite carries a failing case of its own. The bound is held by an "
        "`assert()` in the helper.",
        {"check-predicate-removed-by-default-build"},
    ),
    (
        # The predicate SHAPE §7.7's boxed RULE names, carried by a clause with
        # NO assertion noun in it: `without asserting` is the verdict's shape
        # and `asserting` is not a spelling the noun pattern reads. So this
        # mutation reddens the shape rule ALONE, which is what proves the two
        # rules are separately falsifiable rather than one rule wearing two
        # names.
        "a Check: verdict that rests on an assertion not firing",
        "Registered with `add_test(NAME t0_beta ...)` through the track test list.",
        "Registered with `add_test(NAME t0_beta ...)` through the track test list. "
        "The test drives the case and verifies it completes without asserting.",
        {"check-verdict-rests-on-an-assertion-not-firing"},
    ),
    (
        "a completion marker written in the grammar that predates the form",
        "`add_test(NAME t2_zeta ...)`.",
        "`add_test(NAME t2_zeta ...)`.\n**DONE on 2026-01-01, commit `1111111`.**",
        # DDD-2's marker is live and DDD-1 carries none, so the completion gate
        # reports the pair as well. Two true statements about one edit.
        {"done-marker-citation-not-in-form", "done-marker-over-incomplete-dependency"},
    ),
    # ------------------------------------------------------------------- gate
    (
        "a completion marker over a dependency that carries none",
        "Check: `ctest --test-dir build --no-tests=error -R t0_beta`. Registered "
        "with `add_test(NAME t0_beta ...)` through the track test list.",
        "Check: `ctest --test-dir build --no-tests=error -R t0_beta`. Registered "
        "with `add_test(NAME t0_beta ...)` through the track test list.\n"
        "**DONE on 2026-01-02. CITED PER DECLARED PATH:** `axiomantic/core` "
        "`2222222` \u2192 `testdata/synth/`, `testdata/shared.json`, "
        "`tests/t0_beta.cpp`, `tests/tests_core.cmake`.",
        {"done-marker-over-incomplete-dependency"},
    ),
    (
        # ONE replacement spanning two blocks, because the pair this rule reads
        # has two ends: the marker goes on DDD-2 and the substitute goes on the
        # dependency DDD-1. Marking DDD-2 alone would earn the ERROR rule above
        # instead, so the two edits cannot be split into two mutations.
        "a completion marker over a dependency the plan does not schedule",
        "**DDD-1 \u00b7 The Python half** \u2014 T0\n"
        "Files: `tools/test_delta.py`, `testdata/shared.json`\n"
        "Design: 6\n"
        "Depends: AAA-2\n"
        "Check: `pytest tools/test_delta.py`. The suite carries a failing case "
        "of its own.\n"
        "\n"
        "**DDD-2 \u00b7 The oracle comparison** \u2014 T2\n"
        "Files: `tests/t2_zeta.cpp`, `tests/tests_core.cmake`\n"
        "Design: 7\n"
        "Depends: DDD-1\n"
        "Check: `ctest --test-dir build --no-tests=error -R '^t2_zeta$'`. "
        "Registered with `add_test(NAME t2_zeta ...)`.",
        "**DDD-1 \u00b7 The Python half** \u2014 OPERATOR\n"
        "Files: `tools/test_delta.py`, `testdata/shared.json`\n"
        "Design: 6\n"
        "Depends: AAA-2\n"
        "Check: `pytest tools/test_delta.py`. The suite carries a failing case "
        "of its own.\n"
        "\n"
        "**DDD-2 \u00b7 The oracle comparison** \u2014 T2\n"
        "Files: `tests/t2_zeta.cpp`, `tests/tests_core.cmake`\n"
        "Design: 7\n"
        "Depends: DDD-1\n"
        "Check: `ctest --test-dir build --no-tests=error -R '^t2_zeta$'`. "
        "Registered with `add_test(NAME t2_zeta ...)`.\n"
        "**DONE on 2026-01-03. CITED PER DECLARED PATH:** `axiomantic/core` "
        "`3333333` \u2192 `tests/t2_zeta.cpp`, `tests/tests_core.cmake`.",
        {"done-marker-over-a-dependency-this-plan-does-not-schedule"},
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
    to a lint is a rule this file already knows about.

    A rule id reaches a `Finding` two ways. Most lints spell it at the `Finding`
    call. `removed` spells it on a DATA ROW and passes `rule=predicate.rule`,
    because a rule id spelled in the rule body is the roster defect in its
    smallest form. Both are `rule=` keywords carrying a string literal, so both
    are read the same way and neither needs this function to know a lint's name.

    A module that DECLARES rule ids is described by those declarations. A module
    that declares none is described by what its `Finding` calls name, literal or
    not, so a rule the source cannot name is reported rather than skipped rather
    than a lint going silently uncovered.

    THE GAP THIS LEAVES, NAMED: a module that declares rule ids AND ALSO builds
    one from an expression naming none of them would have that one missed here.
    `test_every_document_lint_owns_at_least_one_covered_rule` is what catches the
    whole-module case; a partial one would need a reader that can resolve the
    expression, which no reader here does.
    """
    tree = ast.parse(pathlib.Path(module.__file__).read_text(encoding="utf-8"))
    declared = set()
    emitted = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        found = [keyword.value for keyword in node.keywords if keyword.arg == "rule"]
        if getattr(node.func, "id", "") == "Finding":
            for value in found + node.args[:1]:
                emitted.add(
                    value.value if isinstance(value, ast.Constant) else ast.unparse(value)
                )
        declared |= {
            value.value for value in found if isinstance(value, ast.Constant)
        }
    return declared or emitted


def rules_the_lints_emit():
    out = set()
    for module in (
        graph, waves, tiers, checks, counts, implicit, registrar, closure,
        structure, anchors, markers, secondwrite, removed, gate,
    ):
        out |= rules_in_source(module)
    return out


class RuleReaderTest(unittest.TestCase):
    """`rules_in_source` drives every assertion in `RuleCoverageTest`. A reader
    that returned an empty set, or that went blind when a lint moved its rule
    ids onto a data row, would make all of them pass and verify nothing.

    So the reader is driven here directly, in BOTH of its branches, over sources
    written for the purpose.
    """

    def read(self, source):
        path = pathlib.Path(self.enterContext(tempfile.TemporaryDirectory())) / "m.py"
        path.write_text(source, encoding="utf-8")
        return rules_in_source(types.SimpleNamespace(__file__=str(path)))

    def test_a_rule_spelled_at_the_finding_call_is_read(self):
        self.assertEqual(
            self.read('Finding(rule="spelled-at-the-call", message="")'),
            {"spelled-at-the-call"},
        )

    def test_a_rule_declared_on_a_data_row_is_read(self):
        """The branch `removed` uses. Without it that lint reads as owning the
        single pseudo-rule `predicate.rule` and every rule it really emits goes
        uncovered with this file green."""
        self.assertEqual(
            self.read(
                'ROWS = (Predicate(rule="declared-on-a-row"),)\n'
                "Finding(rule=predicate.rule, message='')\n"
            ),
            {"declared-on-a-row"},
        )

    def test_a_rule_the_source_cannot_name_is_reported_and_not_skipped(self):
        """The other branch. A module that declares nothing and builds its rule
        from an expression is REPORTED under that expression, which no mutation
        covers, so `test_every_rule_the_lints_emit_has_a_mutation` fails by
        name rather than passing over a rule nothing drives."""
        self.assertEqual(
            self.read("Finding(rule=chosen.rule, message='')"),
            {"chosen.rule"},
        )

    def test_the_reader_is_not_empty_for_the_lint_that_declares_its_rules(self):
        """An empty scan makes every assertion in `RuleCoverageTest` pass."""
        self.assertEqual(
            rules_in_source(removed),
            {
                "check-predicate-removed-by-default-build",
                "check-verdict-rests-on-an-assertion-not-firing",
            },
        )


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

    def test_every_mutation_changes_something(self):
        """A mutation whose replacement equals its anchor AND which overrides no
        `build_dirs` mutates nothing. The run is then the clean fixture itself,
        the expected rule set is whatever the clean fixture already reports, and
        the subtest passes while covering no rule at all.

        The two ways a defect is injected are BOTH allowed and the predicate
        names both: the text is replaced with different text, or the fifth
        element supplies a build directory the clean text cannot describe.
        `an invalid build-dir path` is the second kind and is the reason this
        assertion reads `and` rather than testing the text alone."""
        self.assertEqual(
            [item[0] for item in MUTATIONS if item[1] == item[2] and len(item) <= 4],
            [],
        )

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
        self.assertEqual(len(MUTATIONS), 63)

    def test_the_rule_count_is_the_one_the_review_measured(self):
        self.assertEqual(len(rules_the_lints_emit()), 63)

    def test_every_document_lint_owns_at_least_one_covered_rule(self):
        modules = {
            "graph": graph, "waves": waves, "tiers": tiers, "checks": checks,
            "counts": counts, "implicit": implicit, "registrar": registrar,
            "closure": closure, "structure": structure, "anchors": anchors,
            "markers": markers, "secondwrite": secondwrite, "removed": removed,
            "gate": gate,
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
