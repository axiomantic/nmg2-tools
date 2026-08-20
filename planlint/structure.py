"""Lint 10 — document structure.

A parse failure must never present as a clean result.

Defect L-5 is the reason this module exists. The backtick scanner paired ticks
across a whole task body, so a fenced block — which opens with THREE of them —
inverted every pairing after itself, and everything below the first fence in a
body became invisible. The lint went blind and said nothing, and the warning
count fell as text was added, which reads as an improvement.

`planlint.document` now scans fences as REGIONS and reads an unmatched backtick
as literal text, so neither shape can hide a name any more. That is the repair.
This is the alarm, and the two are not the same thing: a scanner that copes
quietly with broken markup is one edit away from coping quietly with something
it should not. Both breakages are therefore findings of their own.

  * `unmatched-backtick` — a task body carrying a backtick with no partner on
    its own line. The markup is wrong whatever the scanner makes of it.
  * `unclosed-fence` — a fence opened and never closed. Section 7.7's whole
    fenced-block scope depends on knowing where a fence ends, and the parser
    reads a fence with no partner as no fence at all, so every boundary below
    it is the wrong one.
  * `done-marker-not-line-anchored` — a completion marker written behind a
    lead-in. Section 24.6's census reads `^\\*\\*DONE`, and it anchors the
    pattern for a reason it states: a `**DONE` inside a half-state table row
    belongs to a half of a task. The anchor does that, and it also drops every
    task-level marker written behind a lead-in, as a smaller number with
    nothing to read as an error. Repairing a census leaves the next pattern
    free to be wrong the same way; this removes the freedom, so a document this
    lint passes is one on which the anchored form and the wide form of
    `planlint.document` return the same set.

All three are ERRORs. A document a lint cannot read correctly is not a document
that passed.
"""

import re

from planlint.document import (
    DONE_MARKER,
    FENCE,
    TABLE_ROW,
    TABLE_RULE,
    fenced_line_indexes,
    inline_code_spans,
)
from planlint.finding import ERROR, Finding, guard_no_input

# A `|` that belongs to a cell is written `\|`. Counting raw pipes reports the
# escaped spelling — the REPAIR — beside the defect, and a rule that fires on
# correct input trains a reader to ignore it.
UNESCAPED_PIPE = re.compile(r"(?<!\\)\|")


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

    The document's own fence scan drops such a fence in silence. This reads the
    same lines and keeps what that scan discards.
    """
    open_at = 0
    for index, line in enumerate(doc.lines):
        if FENCE.match(line):
            open_at = 0 if open_at else index + 1
    return open_at


def table_blocks(doc):
    """Every run of contiguous table lines, as `[first index, last index]`.

    Fenced lines are excluded: a fence is a quotation, and a table quoted
    inside one is never rendered as a table.
    """
    fenced = fenced_line_indexes(doc.lines)
    blocks = []
    open_at = None
    for index, line in enumerate(doc.lines):
        if index not in fenced and TABLE_ROW.match(line):
            open_at = index if open_at is None else open_at
            continue
        if open_at is not None:
            blocks.append([open_at, index - 1])
            open_at = None
    if open_at is not None:
        blocks.append([open_at, len(doc.lines) - 1])
    return blocks


def column_norm(doc, block):
    """`(the delimiter row's unescaped pipe count, its 1-based line)`, or `None`.

    Markdown fixes a table's column count at its DELIMITER row, so that row is
    the norm rather than the most common count among the rows. The two agree on
    this document today; they part on a table whose MAJORITY of rows is broken,
    and there the delimiter row is still the count the renderer uses.

    WHAT THIS CANNOT DECIDE: a table that carries no delimiter row states no
    column count of its own, and nothing here supplies one. A one-row table is
    that case, and it is returned as undecided rather than as a norm of one.
    """
    for index in range(block[0], block[1] + 1):
        if TABLE_RULE.match(doc.lines[index]):
            return len(UNESCAPED_PIPE.findall(doc.lines[index])), index + 1
    return None


def _first_cell(line):
    """The text of a row's first cell, which is the row's own identifier.

    The evidence names the first cell and never the whole row. A row of this
    plan's section 24.6 runs to thousands of characters, and a finding that
    printed one whole would bury the eight it reports in the report itself.
    """
    parts = UNESCAPED_PIPE.split(line)
    return parts[1].strip() if len(parts) > 2 else line.strip()


def table_row_column_counts(doc):
    """Every table row whose cell count is not the one its table declares."""
    out = []
    for block in table_blocks(doc):
        norm = column_norm(doc, block)
        if norm is None:
            continue
        count, rule_line = norm
        for index in range(block[0], block[1] + 1):
            if TABLE_RULE.match(doc.lines[index]):
                continue
            found = len(UNESCAPED_PIPE.findall(doc.lines[index]))
            if found != count:
                out.append((index + 1, found, count, rule_line))
    return out


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

    for marker in doc.done_markers:
        if marker.anchored:
            continue
        task = doc.task(marker.task)
        findings.append(
            Finding(
                rule="done-marker-not-line-anchored",
                message=(
                    "a completion marker does not open its line. A census "
                    "anchored at the start of the line does not see it, and the "
                    "shortfall arrives as a smaller number rather than as an "
                    "error"
                ),
                task=marker.task,
                section=task.section if task else "",
                line=marker.line,
                evidence=(
                    f"line {marker.line} carries a `{DONE_MARKER}` marker that "
                    f"does not open the line: `{marker.text}`. A census "
                    "anchored at the start of the line reads this task as "
                    "unmarked"
                ),
                severity=ERROR,
            )
        )

    for line, found, norm, rule_line in table_row_column_counts(doc):
        findings.append(
            Finding(
                rule="table-row-column-count",
                message=(
                    "a table row carries a different number of unescaped `|` "
                    "characters than the delimiter row of its own table. "
                    "Markdown fixes the column count at the delimiter row, so "
                    "this row renders with the wrong number of cells and every "
                    "reader — a person and a lint — reads the wrong text in the "
                    "wrong column"
                ),
                section=doc.section_at(line),
                line=line,
                evidence=(
                    f"line {line} carries {found} unescaped `|` characters and "
                    f"the delimiter row at line {rule_line} carries {norm}. The "
                    f"row opens `{_first_cell(doc.lines[line - 1])}` and a `|` "
                    "that belongs to a cell is written `\\|`"
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
