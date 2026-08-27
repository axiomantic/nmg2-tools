"""Lint 10 — document structure.

A parse failure must never present as a clean result.

Defect L-5 is the reason this module exists. The backtick scanner paired ticks
across a whole task body, so a fenced block — which opens with THREE of them —
inverted every pairing after itself, and everything below the first fence in a
body became invisible. The lint went blind and said nothing. Measured on the
real plan: five task bodies gained a transcript and the warning count moved
from 169 DOWN to 166, which reads as an improvement.

`planlint.document` now scans fences as REGIONS and reads an unmatched backtick
as literal text, so neither shape can hide a name any more. That is the repair.
This is the alarm, and the two are not the same thing: a scanner that copes
quietly with broken markup is one edit away from coping quietly with something
it should not. Both breakages are therefore findings of their own.

  * `unmatched-backtick` — a task body carrying a backtick with no partner on
    its own line. Every name after it was read as prose before the repair, and
    the markup is wrong either way.
  * `unclosed-fence` — a fence opened and never closed. Section 7.7's whole
    fenced-block scope depends on knowing where a fence ends, and the parser
    reads a fence with no partner as no fence at all, so every boundary below
    it is the wrong one.

The line this rule reports is the line `planlint.document.fence_regions` failed
to close, read out of that scan rather than counted again here. Which marker
closes a fence is CommonMark 4.5's question and not a matter of position: a
closing fence carries no info string and is at least as long as the opener, so a
fence quoting another fence closes where it really closes. A second pairing rule
written beside this one would be a second reading of the same document, and the
two would disagree on exactly the documents that matter.

Both are ERRORs. A document a lint cannot read correctly is not a document that
passed.
"""

from planlint.document import fence_regions, inline_code_spans
from planlint.finding import ERROR, Finding, guard_no_input


def _line_at(text, offset):
    """The 1-based line number an offset falls on, within a run of text."""
    return text.count("\n", 0, offset) + 1


def unmatched_backticks(task):
    """`{line number in the document: count}` for one task body."""
    _, unmatched = inline_code_spans(task.body_text)
    out = {}
    for offset in unmatched:
        line = task.line + _line_at(task.body_text, offset) - 1
        out[line] = out.get(line, 0) + 1
    return out


def unclosed_fence_line(doc):
    """The 1-based line of a fence with no partner, or 0.

    The document's own fence scan drops such a fence in silence. This reads it
    out of `fence_regions`, the same scan, so the line reported here is the line
    the parser actually failed to close and never a different marker.
    """
    _regions, open_at = fence_regions(doc.lines)
    return 0 if open_at is None else open_at + 1


def run(doc):
    findings = []

    for task in doc.tasks:
        counts = unmatched_backticks(task)
        body = task.body_text.split("\n")
        for line in sorted(counts):
            count = counts[line]
            written = body[line - task.line]
            findings.append(
                Finding(
                    rule="unmatched-backtick",
                    message=(
                        "a task body carries a backtick with no partner on its own "
                        "line. The scanner reads it as literal text, so nothing is "
                        "hidden — but the markup does not say what it looks like it "
                        "says, and a reader and a lint read two different documents"
                    ),
                    task=task.ident,
                    section=task.section,
                    line=line,
                    evidence=(
                        f"line {line} carries {count} backtick"
                        f"{'' if count == 1 else 's'} with no partner on its own "
                        f"line: `{written}`. Every name after it in this body reads "
                        "as prose"
                    ),
                    severity=ERROR,
                )
            )

    opened = unclosed_fence_line(doc)
    if opened:
        findings.append(
            Finding(
                rule="unclosed-fence",
                message=(
                    "a fenced block is opened and never closed. Section 7.7 scopes "
                    "a check lint by where a fence starts and ends, and a fence "
                    "with no partner is read as no fence at all"
                ),
                section="7.7 The scope a check lint may read",
                line=opened,
                evidence=(
                    f"line {opened} opens a fenced block and no line below it "
                    f"closes the fence; every fenced-block rule below line "
                    f"{opened} reads the document with the wrong boundaries"
                ),
                severity=ERROR,
            )
        )

    return guard_no_input(
        "structure", findings, len(doc.tasks), "task bodies", "structure lint"
    )
