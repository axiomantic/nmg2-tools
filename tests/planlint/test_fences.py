"""Tests for fence-aware and unmatched-backtick scanning — defect L-5.

A fenced block opens with THREE backticks. The scanner paired backticks across
a whole task body, so a fence left two backticks over and every pairing after
it was inverted: text that is prose read as a quoted span, and every backticked
name read as prose. Everything after the first fence in a task body was
invisible to the lint.

The defect is expensive in the direction that hides it. Adding transcripts to
five task bodies of the real plan moved the warning count from 169 to 166 —
DOWN, which reads as an improvement, while three real findings went silent.

The four shapes are pinned here:

  * a body with a fence yields the same findings AFTER the fence as a body
    without one;
  * five bodies gaining transcripts do not reduce the finding count;
  * the two real bodies that are blind today — the `SCH-12` shape and the
    `PLG-10` shape — report their qualified names again;
  * an unmatched INLINE backtick does not swallow the rest of the body either.
    That is the same defect in a smaller shape.
"""

import unittest

from planlint import closure, structure
from planlint.document import PlanDocument, fenced_line_indexes

PRODUCER = (
    "**AAA-1 · The producer** — T0\n"
    "Files: `g2Lib/scheduler.h`\n"
    "Depends: none\n"
    "Check: The header declares `Scheduler::Config`.\n"
    "\n"
)


def reader(number, body):
    """One reader task whose gate reads a symbol the producer exports."""
    return (
        f"**BBB-{number} · The reader {number}** — T0\n"
        f"Files: `g2Lib/test/t1_gate{number}.cpp`\n"
        "Depends: none\n"
        f"Check: `ctest --test-dir build --no-tests=error -R ^t1_gate{number}$`."
        f"{body}\n"
        "\n"
    )


def transcript(number):
    """The shell transcript section 7.7 lets a task print beside its check."""
    return (
        "\n"
        "```\n"
        f"$ ctest --test-dir build --no-tests=error -R ^t1_gate{number}$\n"
        f"Test #1: t1_gate{number} ... Passed\n"
        "```\n"
    )


READS = " The gate reads `Scheduler::Config`."


def findings_of(text):
    """`(rule, task, severity)` for every closure finding, in report order."""
    doc = PlanDocument.from_text(text, name="inline")
    return [(f.rule, f.task, f.severity) for f in closure.run(doc).findings]


class FenceTransparencyTest(unittest.TestCase):
    """A fence is a region. It must not change what the text around it says."""

    WITHOUT = PRODUCER + reader(1, READS)
    WITH = PRODUCER + reader(1, transcript(1) + READS.lstrip())

    def test_a_body_without_a_fence_reports_the_unreachable_producer(self):
        """The control. Without this the next assertion could pass on two
        empty lists and prove nothing."""
        self.assertEqual(
            findings_of(self.WITHOUT),
            [("symbol-producer-unreachable", "BBB-1", "ERROR")],
        )

    def test_a_fence_does_not_hide_the_finding_after_it(self):
        self.assertEqual(
            findings_of(self.WITH),
            [("symbol-producer-unreachable", "BBB-1", "ERROR")],
        )

    def test_the_fence_leaves_the_consumption_list_unchanged(self):
        """The finding list is downstream of the consumption list. Pinning the
        consumption itself names WHICH read went missing, not merely that a
        count moved."""
        with_fence = PlanDocument.from_text(self.WITH, name="inline")
        without_fence = PlanDocument.from_text(self.WITHOUT, name="inline")

        self.assertEqual(
            [
                (c.symbol, c.kind, c.verb, c.hedged)
                for c in closure.consumptions(with_fence, with_fence.task("BBB-1"))
            ],
            [("Scheduler::Config", "symbol", "reads", False)],
        )
        self.assertEqual(
            [
                (c.symbol, c.kind, c.verb, c.hedged)
                for c in closure.consumptions(
                    without_fence, without_fence.task("BBB-1")
                )
            ],
            [("Scheduler::Config", "symbol", "reads", False)],
        )


class TranscriptRegressionTest(unittest.TestCase):
    """The measured regression, in the shape it was measured in.

    Five task bodies gained a transcript and the plan's warning count FELL by
    three. A count that falls when text is added is the signature of a scanner
    going blind, so the count is pinned here in both directions.
    """

    BEFORE = PRODUCER + "".join(reader(n, READS) for n in range(1, 6))
    AFTER = PRODUCER + "".join(
        reader(n, transcript(n) + READS.lstrip()) for n in range(1, 6)
    )

    EXPECTED = [
        ("symbol-producer-unreachable", f"BBB-{n}", "ERROR") for n in range(1, 6)
    ]

    def test_five_bodies_without_transcripts_report_five_findings(self):
        self.assertEqual(findings_of(self.BEFORE), self.EXPECTED)

    def test_five_bodies_gaining_transcripts_report_the_same_five_findings(self):
        self.assertEqual(findings_of(self.AFTER), self.EXPECTED)

    def test_adding_the_transcripts_never_lowers_the_count(self):
        """Stated as the inequality the defect broke, so that a future change
        that trades one finding for another still fails here."""
        self.assertGreaterEqual(
            len(findings_of(self.AFTER)), len(findings_of(self.BEFORE))
        )
        self.assertEqual(len(findings_of(self.AFTER)), 5)


class BlindBodyTest(unittest.TestCase):
    """The two task bodies of the real plan that are blind today.

    Both carry a fence and both hold a qualified name after it. The lint
    reports zero qualified spans in each, so the names are invisible. The
    bodies are reproduced in the shape the plan writes them.
    """

    SCH12 = (
        "**SCH-8 · The allocator** — T0\n"
        "Files: `g2Lib/jitConfig.h`\n"
        "Depends: none\n"
        "Check: The header declares `JitConfig::maxInstructionsPerBlock`.\n"
        "\n"
        "**SCH-12 · The cycle-debt rule** — T0\n"
        "Files: `g2Lib/cycleDebt.h`, `g2Lib/test/t0_cycle_debt.cpp`\n"
        "Depends: none\n"
        "Check: `ctest --test-dir build --no-tests=error -R ^t0_cycle_debt$`. "
        "The per-quantum loop is exactly:\n"
        "```\n"
        "budget = (int64) alloc(ctx.rate, &ctx.acc);\n"
        "want   = budget - ctx.debt;\n"
        "```\n"
        "Register rows 2 to 4 leave `JitConfig::maxInstructionsPerBlock` at the "
        "upstream default of `0`, which means uncapped.\n"
    )

    PLG10 = (
        "**PLG-9 · The status surface** — T0\n"
        "Files: `g2Lib/status.h`\n"
        "Depends: none\n"
        "Check: The header declares `Status::BadLookahead`.\n"
        "\n"
        "**PLG-10 · The reported latency** — T0\n"
        "Files: `g2JucePlugin/g2Plugin.cpp`, `g2Lib/test/t0_latency_formula.cpp`\n"
        "Depends: none\n"
        "Check: `ctest --test-dir build --no-tests=error -R ^t0_latency_formula$`. "
        "The formula is computed once:\n"
        "```\n"
        "D_total(R) = ceil( (L + D_chain) * R / G2_FRAME_RATE_HZ )\n"
        "```\n"
        "The test drives a value above the bound and asserts "
        "`Status::BadLookahead`.\n"
    )

    def qualified_spans(self, text, ident):
        doc = PlanDocument.from_text(text, name="inline")
        _, spans = closure.mask_backticks(doc.task(ident).body_text)
        return [inner for _, _, inner in spans if closure.QUALIFIED.match(inner)]

    def test_the_sch_12_shape_sees_its_qualified_name_again(self):
        self.assertEqual(
            self.qualified_spans(self.SCH12, "SCH-12"),
            ["JitConfig::maxInstructionsPerBlock"],
        )

    def test_the_sch_12_shape_reports_the_name_it_cannot_reach(self):
        self.assertEqual(
            findings_of(self.SCH12),
            [("symbol-closure-candidate", "SCH-12", "WARNING")],
        )

    def test_the_plg_10_shape_sees_its_qualified_name_again(self):
        self.assertEqual(
            self.qualified_spans(self.PLG10, "PLG-10"), ["Status::BadLookahead"]
        )

    def test_the_plg_10_shape_reports_the_name_it_cannot_reach(self):
        self.assertEqual(
            findings_of(self.PLG10),
            [("symbol-closure-candidate", "PLG-10", "WARNING")],
        )


class UnmatchedInlineBacktickTest(unittest.TestCase):
    """The same defect in a smaller shape.

    One unmatched inline backtick paired with the NEXT backtick on a later
    line, which put the prose between them inside a quoted span and put the
    quoted name outside it. CommonMark reads an unclosed backtick as literal
    text, and so does this scanner: the span never crosses a line break.
    """

    PLAN = PRODUCER + reader(
        1,
        " The name `Scheduler is written with one backtick.\n"
        "The gate reads `Scheduler::Config`.",
    )

    def test_an_unmatched_backtick_does_not_swallow_the_rest_of_the_body(self):
        self.assertEqual(
            findings_of(self.PLAN),
            [("symbol-producer-unreachable", "BBB-1", "ERROR")],
        )

    def test_the_unmatched_backtick_is_literal_and_opens_no_span(self):
        doc = PlanDocument.from_text(self.PLAN, name="inline")
        _, spans = closure.mask_backticks(doc.task("BBB-1").body_text)

        self.assertEqual(
            [inner for _, _, inner in spans],
            [
                "g2Lib/test/t1_gate1.cpp",
                "ctest --test-dir build --no-tests=error -R ^t1_gate1$",
                "Scheduler::Config",
            ],
        )


class FencePairingTest(unittest.TestCase):
    """CommonMark 4.5 decides which marker closes a fence, and the two rules
    that decide it are the two the scan did not read.

    A closing fence carries NO info string and is AT LEAST as long as the
    opener. A line that breaks either rule is CONTENT, not a marker. Without
    those rules the scan pairs markers by position alone, so a fence documenting
    another fence -- the shape any document about markdown carries -- closes at
    the wrong line: the region below it is left unmasked, and the real closer is
    then read as an opener with no partner, which is a false `unclosed-fence`
    against a well-formed document.
    """

    # `structure.run` guards on an empty scan, so a document with no task at
    # all cannot report a clean verdict. One well-formed task is what lets the
    # verdict below be a reading and not the guard.
    TASK = "\n".join(
        [
            "",
            "**AAA-1 \u00b7 A task** \u2014 T0",
            "Files: `src/one.cpp`",
            "Depends: none",
            "Check: `ctest --test-dir build --no-tests=error -R ^t0_alpha$`",
            "",
        ]
    )

    INFO_STRING = "\n".join(
        ["before", "```", "```python", "code", "```", "after"]
    )
    LONGER_OPENER = "\n".join(
        ["before", "````", "```", "code", "```", "````", "after"]
    )

    def test_a_marker_carrying_an_info_string_cannot_close_a_fence(self):
        self.assertEqual(
            sorted(fenced_line_indexes(self.INFO_STRING.split("\n"))),
            [1, 2, 3, 4],
        )

    def test_a_run_shorter_than_the_opener_cannot_close_it(self):
        self.assertEqual(
            sorted(fenced_line_indexes(self.LONGER_OPENER.split("\n"))),
            [1, 2, 3, 4, 5],
        )

    def test_neither_shape_is_reported_as_an_unclosed_fence(self):
        """Both documents are well formed. A lint that reports one is telling a
        reader to repair markup that is already correct."""
        for label, text in (
            ("info string", self.INFO_STRING),
            ("longer opener", self.LONGER_OPENER),
        ):
            with self.subTest(shape=label):
                doc = PlanDocument.from_text(text + self.TASK, name="inline")
                self.assertEqual(structure.unclosed_fence_line(doc), 0)
                result = structure.run(doc)
                self.assertEqual([f.rule for f in result.findings], [])
                self.assertEqual(result.failed, False)

    def test_a_fence_that_never_closes_is_still_reported(self):
        """The control. The rules above only ever REFUSE a closer, so a fence
        with none must still be found, and at the line that opened it."""
        doc = PlanDocument.from_text(
            "\n".join(["before", "```", "```python", "code", "after"]),
            name="inline",
        )
        self.assertEqual(structure.unclosed_fence_line(doc), 2)
        self.assertEqual(fenced_line_indexes(doc.lines), set())

    def test_a_task_header_quoted_inside_such_a_fence_is_not_a_task(self):
        """The masking half, at the level a lint reads. A plan that QUOTES a
        task block inside a fence that documents markdown must not gain a task
        from the quotation."""
        text = "\n".join(
            [
                "**AAA-1 \u00b7 The real task** \u2014 T0",
                "Files: `src/one.cpp`",
                "Depends: none",
                "Check: `ctest --test-dir build --no-tests=error -R ^t0_alpha$`",
                "",
                "````",
                "```markdown",
                "**ZZZ-9 \u00b7 A quoted task** \u2014 T0",
                "Files: `src/quoted.cpp`",
                "Depends: none",
                "Check: `ctest --test-dir build --no-tests=error -R ^t0_quoted$`",
                "```",
                "````",
            ]
        )
        doc = PlanDocument.from_text(text, name="inline")
        self.assertEqual([task.ident for task in doc.tasks], ["AAA-1"])


if __name__ == "__main__":
    unittest.main()
