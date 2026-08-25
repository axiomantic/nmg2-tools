"""Lint 15 — a `Check:` predicate that names a mechanism the default build removes.

Section 7.7 measurements 7 and 8: the default build is Release, Release defines
`NDEBUG`, and `NDEBUG` removes every `assert()`. A check whose verdict rests on
an assertion firing therefore reports PASS against a tree in which the property
was never written.

The mechanism list is a DATA TABLE this module iterates and never a pattern in
`run()`. Section 24.6 row W3-404 states the reason in its own words — "a roster
amended once per case is a missing predicate" — and a lint that hardcoded the
one `assert()` regex would be row W3-4's roster rewritten in Python. Adding
member two is a row and a fixture, never a second rule and never an edit here.

The two discriminating fields are LITERAL patterns and not English. Row W3-405
measured what an English description costs: `kept_by` matches DEBUG-flavoured
build-type names and nothing else, because `Release` and `NDEBUG` are the
settings that REMOVE the mechanism. A `kept_by` reaching either would spare
exactly the blocks whose own prose diagnoses the defect — DSP-7 first of all,
whose `Check:` block names both in the sentence that convicts it.
"""

import dataclasses
import re

from planlint.document import sentences
from planlint.finding import ERROR, Finding, guard_no_input


@dataclasses.dataclass(frozen=True)
class RemovedMechanism:
    """One mechanism a build setting deletes, and how a block names it.

    `clause_pattern` reads the MECHANISM — the call and its noun — and not the
    English verb `asserts`, which is what a test does in every build and names
    no mechanism at all.
    """

    mechanism: str
    clause_pattern: str
    removed_by: str
    kept_by: str
    authority: str


REMOVED_MECHANISMS = (
    RemovedMechanism(
        mechanism="assert()",
        clause_pattern=r"(?i)\bassert\(\)|\bassert(?:ion|ions)\b",
        removed_by="NDEBUG",
        # Measurement 7 measures the `dsp56300` default build and measurement 8
        # the `gearmulator` fork. Every block this lint is calibrated on is a
        # `gearmulator`-fork task, and section 7.7 forbids applying a measured
        # behaviour outside its own transcript.
        kept_by=r"(?i)\bdebug\s+build\b|\bdebug-only\b|\bRelWithDebInfo\b"
        r"|\bCMAKE_BUILD_TYPE\s*=\s*Debug\b",
        authority="§7.7 measurements 7 and 8",
    ),
)


def _block_lines(doc, task):
    """The `Check:` BLOCK as document lines, with each line's number.

    The extent is the `Check:` line THROUGH THE END OF THE TASK BODY, because a
    sparing phrase can sit anywhere in the body, and it is the extent
    `check_text` holds and what section 7.7.1 condition 8 means by the term.

    It must be the SAME extent, and not merely the same range. `check_text` is
    built with every `$ ` transcript fence dropped and the `Check: ` field
    label stripped, so a reader that re-walked the raw lines could quote a
    shell transcript as the predicate the detection flagged — a record of a
    measurement, which `planlint.document` states is never an instruction, and
    a line the detection never read. The two exclusions are reproduced here.

    `doc._in_fence` is a private member and it is used deliberately: the
    transcript flag lives only there. The public `fenced_line_indexes` does not
    discriminate a transcript from any other fence, so it would exclude the
    non-transcript fences `check_text` KEEPS and reintroduce the same
    disagreement in the other direction.

    The label is not stripped by a second reading of `FIELD`, which is the
    document's own regex and has exactly one user by assertion. The parser
    already wrote the stripped value down: it is the FIRST line of
    `check_text`, so that is what the `Check:` line contributes here.
    """
    end = task.line + len(task.body_text.split("\n"))
    check_value = task.check_text.splitlines()[0]
    block = []
    for number in range(task.check_line, end):
        fence = doc._in_fence(number - 1)
        if fence and fence["transcript"]:
            continue
        text = check_value if number == task.check_line else doc.lines[number - 1]
        block.append((number, text))
    return block


def _clause(doc, task, pattern):
    """The line and the sentence a match sits on, quoted verbatim.

    A reader told a `Check:` is unfalsifiable and not shown the sentence goes
    looking for it.
    """
    for number, text in _block_lines(doc, task):
        if not pattern.search(text):
            continue
        for sentence in sentences(text):
            if pattern.search(sentence):
                return number, sentence
        return number, text.strip()
    return task.check_line, task.check_text.splitlines()[0].strip()


def run(doc, mechanisms=REMOVED_MECHANISMS):
    findings = []
    examined = 0

    for task in doc.tasks:
        if not task.check_line or not task.check_text.strip():
            continue
        examined += 1
        for mechanism in mechanisms:
            clause_pattern = re.compile(mechanism.clause_pattern)
            if not clause_pattern.search(task.check_text):
                continue
            if re.search(mechanism.kept_by, task.check_text):
                continue
            line, evidence = _clause(doc, task, clause_pattern)
            findings.append(
                Finding(
                    rule="check-predicate-removed-by-default-build",
                    message=(
                        f"a Check: predicate names {mechanism.mechanism}, which "
                        f"{mechanism.removed_by} removes from the default build, so the "
                        "check reports PASS against a tree in which the property was "
                        "never written; the block names no build type that keeps it "
                        f"({mechanism.authority})"
                    ),
                    task=task.ident,
                    section=task.section,
                    line=line,
                    evidence=evidence,
                    severity=ERROR,
                )
            )

    return guard_no_input(
        "removed", findings, examined, "Check: blocks", "removed-mechanism lint"
    )
